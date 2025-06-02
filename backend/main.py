from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import numpy as np
import cv2
from io import BytesIO
from collections import Counter
from datetime import datetime, timedelta, timezone
import logging
from scipy import ndimage
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="API de Contagem de Colônias",
    description="Processa imagens de placas de Petri para contar e classificar colônias.",
    version="1.6.0" 
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://contadorbacterias.netlify.app"], # Adicione outras origens se necessário para teste local
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-Resumo-Total", "X-Resumo-Amarela", "X-Resumo-Bege", "X-Resumo-Clara", "X-Resumo-Rosada",
        "X-Feedback-Avaliadas", "X-Feedback-Filtradas-Area", "X-Feedback-Filtradas-Circularidade",
        "X-Feedback-Desenhadas", "X-Feedback-Raio-Detectado-Px", # Atualizado
        "X-Feedback-Area-Amostrada-Cm2", # Novo
        "X-Feedback-Densidade-Colonias-Cm2", # Nome consistente
        "X-Feedback-Estimativa-Total-Colonias" # Nome consistente
    ]
)

AREA_PADRAO_PLACA_CM2 = 57.5
MAX_IMAGE_DIM = 1200 

def classificar_cor_hsv(hsv_color_mean):
    h, s, v = hsv_color_mean
    # Tente tornar os ranges um pouco mais permissivos para teste inicial
    if s < 45 and v > 180: # Aumentei s_max para clara, diminuí v_min
        return 'clara'
    elif 18 <= h <= 38 and s > 50 and v > 50: # Ampliei um pouco range de H para amarela, diminuí S e V mínimos
        return 'amarela'
    elif (0 <= h <= 18 or 155 <= h <= 179) and s > 50 and v > 50: # Idem para rosada
        return 'rosada'
    else:
        return 'bege'

def detectar_placa(img_gray):
    start_time = time.time()
    img_blur = cv2.medianBlur(img_gray, 5) 
    
    # Ajustes nos parâmetros de HoughCircles para robustez após redimensionamento
    min_dim_img = min(img_gray.shape[0], img_gray.shape[1])
    min_radius_hough = int(min_dim_img * 0.15) # Raio mínimo como 15% da menor dimensão da imagem
    max_radius_hough = int(min_dim_img * 0.50) # Raio máximo como 50%
    min_dist_hough = min_dim_img // 2 # Distância mínima entre centros de círculos detectados

    # param2 (threshold do acumulador) é crítico. Um valor menor detecta mais círculos (incluindo falsos).
    # Um valor maior é mais restritivo. 30 é um valor comum para começar.
    circulos = cv2.HoughCircles(img_blur, cv2.HOUGH_GRADIENT, dp=1.2, minDist=min_dist_hough,
                                 param1=50, param2=30, minRadius=min_radius_hough, maxRadius=max_radius_hough)

    logger.info(f"Tempo para cv2.HoughCircles: {time.time() - start_time:.4f}s. Parâmetros: dp=1.2, minDist={min_dist_hough}, param1=50, param2=30, minR={min_radius_hough}, maxR={max_radius_hough}")
    if circulos is not None:
        circulos = np.uint16(np.around(circulos))
        # Escolher o melhor círculo (ex: o maior ou o mais central) se múltiplos forem detectados.
        # Por simplicidade, pegamos o primeiro. Mas em imagens ruidosas, pode ser necessário mais lógica.
        best_circle = circulos[0][0] # Poderia ser: max(circulos[0,:], key=lambda c: c[2]) para o de maior raio
        logger.info(f"Placa detectada com centro em ({best_circle[0]}, {best_circle[1]}) e raio {best_circle[2]}")
        return best_circle
    logger.warning("Nenhuma placa detectada na imagem.")
    return None

def processar_imagem(imagem_bytes: bytes, nome_amostra: str, x_manual=None, y_manual=None, r_manual=None):
    total_process_start_time = time.time()
    logger.info(f"[{nome_amostra}] Iniciando processamento da imagem.")

    decode_start_time = time.time()
    file_bytes = np.asarray(bytearray(imagem_bytes), dtype=np.uint8)
    img_original = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    logger.info(f"[{nome_amostra}] Tempo para decodificar imagem: {time.time() - decode_start_time:.4f}s")

    if img_original is None:
        logger.error(f"[{nome_amostra}] Não foi possível decodificar a imagem.")
        raise ValueError("Não foi possível decodificar a imagem.") # Será capturado no endpoint

    resize_start_time = time.time()
    altura_orig, largura_orig = img_original.shape[:2]
    img = img_original.copy() 

    if altura_orig > MAX_IMAGE_DIM or largura_orig > MAX_IMAGE_DIM:
        if altura_orig > largura_orig:
            nova_altura = MAX_IMAGE_DIM
            nova_largura = int(largura_orig * (MAX_IMAGE_DIM / altura_orig))
        else:
            nova_largura = MAX_IMAGE_DIM
            nova_altura = int(altura_orig * (MAX_IMAGE_DIM / largura_orig))
        
        logger.info(f"[{nome_amostra}] Redimensionando imagem de {largura_orig}x{altura_orig} para {nova_largura}x{nova_altura}")
        img = cv2.resize(img_original, (nova_largura, nova_altura), interpolation=cv2.INTER_AREA)
    else:
        logger.info(f"[{nome_amostra}] Imagem já está dentro das dimensões máximas ({largura_orig}x{altura_orig}). Não é necessário redimensionar.")
    
    logger.info(f"[{nome_amostra}] Tempo para redimensionar (se aplicável): {time.time() - resize_start_time:.4f}s")

    desenhar = img.copy()
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    detection_start_time = time.time()
    if x_manual is not None and y_manual is not None and r_manual is not None:
        fator_escala_largura = img.shape[1] / largura_orig
        fator_escala_altura = img.shape[0] / altura_orig
        fator_escala_raio = min(fator_escala_largura, fator_escala_altura)

        x = int(x_manual * fator_escala_largura)
        y = int(y_manual * fator_escala_altura)
        r = int(r_manual * fator_escala_raio)
        logger.info(f"[{nome_amostra}] Usando parâmetros manuais reescalados para a placa: ({x}, {y}, {r})")
    else:
        circulo = detectar_placa(gray)
        if circulo is None:
            logger.warning(f"[{nome_amostra}] Não foi possível detectar a placa automaticamente.")
            raise HTTPException(status_code=422, detail="Não foi possível detectar a placa de Petri automaticamente.")
        x, y, r = circulo
    logger.info(f"[{nome_amostra}] Tempo para detecção da placa: {time.time() - detection_start_time:.4f}s")
    
    if r == 0: # Checagem para evitar divisão por zero mais tarde
        logger.error(f"[{nome_amostra}] Raio da placa detectado como zero. Impossível continuar.")
        raise HTTPException(status_code=422, detail="Raio da placa detectado como zero.")

    processing_core_start_time = time.time()

    r_margem = int(r * 0.90) 
    mask_placa = np.zeros(gray.shape, dtype=np.uint8)
    cv2.circle(mask_placa, (x, y), r_margem, 255, -1)
    
    img_masked = cv2.bitwise_and(img, img, mask=mask_placa)
    gray_masked = cv2.bitwise_and(gray, gray, mask=mask_placa) 
    
    gray_eq = cv2.equalizeHist(gray_masked)
    blurred = cv2.GaussianBlur(gray_eq, (5, 5), 0) # (5,5) é um bom começo

    # Parâmetros do adaptiveThreshold: (src, maxValue, adaptiveMethod, thresholdType, blockSize, C)
    # blockSize deve ser ímpar e maior que o tamanho da característica. C é uma constante.
    thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY_INV, 41, 4) 
    
    opened = cv2.morphologyEx(thresh, cv2.MORPH_OPEN,
                               cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3,3))) # Tente (3,3) para colônias menores
    dist_transform = cv2.distanceTransform(opened, cv2.DIST_L2, 5)
    
    # Ajuste do local_max_filter_size: crucial para segmentação correta
    # Se colônias pequenas estão sendo perdidas, este valor pode ser muito grande.
    # Se colônias grandes estão sendo divididas, pode ser muito pequeno.
    # Vamos começar com um valor menor, ex: 1/100 do raio da placa, com mínimo de 5.
    local_max_filter_size = max(5, int(r / 100 * 2.5) ) # *2.5 para compensar o r_margem, ou use r_margem aqui
    # Ou, um valor fixo pequeno para testar se melhora a detecção de colônias pequenas:
    # local_max_filter_size = 7 # Testar valores ímpares como 5, 7, 9
    logger.info(f"[{nome_amostra}] Usando local_max_filter_size: {local_max_filter_size}")

    local_max = ndimage.maximum_filter(dist_transform, size=local_max_filter_size) == dist_transform
    
    markers, num_features = ndimage.label(local_max) 
    logger.info(f"[{nome_amostra}] Número inicial de marcadores (num_features): {num_features}")

    markers = markers + 1 
    unknown = cv2.subtract(opened, np.uint8(local_max * 255)) 
    markers[unknown == 255] = 0 
    
    watershed_start_time = time.time()
    markers = cv2.watershed(img_masked, markers.astype(np.int32))
    logger.info(f"[{nome_amostra}] Tempo para cv2.watershed: {time.time() - watershed_start_time:.4f}s")

    classificacoes_cores = []
    total_avaliadas = 0
    total_filtradas_area = 0
    total_filtradas_circularidade = 0
    total_desenhadas = 0
    
    fator_escala_area_para_limites = (img.shape[0] * img.shape[1]) / (float(largura_orig * altura_orig) if (largura_orig * altura_orig) > 0 else 1.0)
    
    # AJUSTE INICIAL PARA AREA_MIN_COLONIA - TENTE UM VALOR MENOR
    # Se o tamanho da imagem é ~1200px, e uma colônia tem ~3px de diâmetro, área ~7px.
    # Se a original era 4000px, e o fator de escala linear é ~1/3.3, fator de área ~1/11.
    # Se antes AREA_MIN era 10 na original, agora seria 10/11 ~= 0.9.
    # Vamos tentar um valor absoluto pequeno para começar, ex: 3 pixels de área, e depois refinar.
    AREA_MIN_COLONIA = 4.0  # * fator_escala_area_para_limites # Teste com 4.0 absoluto primeiro.
    AREA_MAX_COLONIA = 500.0 * fator_escala_area_para_limites # Manter um limite superior razoável
    CIRCULARIDADE_MIN = 0.30 # Diminuir um pouco para ser mais permissivo

    logger.info(f"[{nome_amostra}] Usando AREA_MIN_COLONIA: {AREA_MIN_COLONIA:.2f}, AREA_MAX_COLONIA: {AREA_MAX_COLONIA:.2f} (fator_escala_area_para_limites: {fator_escala_area_para_limites:.3f})")
    logger.info(f"[{nome_amostra}] Usando CIRCULARIDADE_MIN: {CIRCULARIDADE_MIN:.2f}")


    loop_marcadores_start_time = time.time()
    colony_details_for_debug = []

    for marker_val in np.unique(markers):
        if marker_val <= 1: 
            continue
        
        mask = np.zeros(gray.shape, dtype=np.uint8)
        mask[markers == marker_val] = 255
        
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        
        cnt = max(contours, key=cv2.contourArea) 
        area = cv2.contourArea(cnt)
        total_avaliadas += 1

        # Log para as primeiras N avaliadas
        # if total_avaliadas <= 20: # Aumentar para ver mais exemplos
        #     logger.info(f"Debug - Avaliando contorno com área: {area:.2f}")

        if area < AREA_MIN_COLONIA or area > AREA_MAX_COLONIA:
            # if total_avaliadas <= 50 and area < AREA_MIN_COLONIA : # Logar algumas que são filtradas por área mínima
            #     logger.info(f"Debug - Filtrada por AREA MIN: {area:.2f} (limite: {AREA_MIN_COLONIA:.2f})")
            total_filtradas_area += 1
            continue

        perimeter = cv2.arcLength(cnt, True)
        if perimeter == 0: 
            continue
        circularity = 4 * np.pi * (area / (perimeter * perimeter))
        if circularity < CIRCULARIDADE_MIN:
            total_filtradas_circularidade += 1
            continue

        (cx, cy), radius_colonia = cv2.minEnclosingCircle(cnt)
        center_colonia = (int(cx), int(cy))
        radius_colonia = int(radius_colonia)

        dist_centro_placa = np.linalg.norm(np.array(center_colonia) - np.array((x, y)))
        if dist_centro_placa > r_margem - radius_colonia : 
             # Se o CENTRO da colônia estiver fora de r_margem, descarte.
             # A condição "r_margem - radius_colonia" é para tentar manter colônias cuja borda toca r_margem mas o centro está dentro.
             # Uma alternativa mais simples é: if dist_centro_placa > r_margem: continue
            continue                                                                              

        mean_color_bgr = cv2.mean(img, mask=mask)[:3] 
        hsv_pixel = cv2.cvtColor(np.uint8([[mean_color_bgr]]), cv2.COLOR_BGR2HSV)
        tipo = classificar_cor_hsv(hsv_pixel[0][0])
        
        # Adicionar detalhes para debug, se necessário
        # colony_details_for_debug.append({'area': area, 'circ': circularity, 'hsv': hsv_pixel[0][0], 'tipo': tipo})

        classificacoes_cores.append(tipo)
        
        if radius_colonia > (r_margem * 0.25): 
             continue

        cor = (0, 0, 255) 
        if tipo == 'amarela':
            cor = (0, 255, 255) 
        elif tipo == 'rosada':
            cor = (203, 192, 255) 
        elif tipo == 'clara':
            cor = (255, 255, 255) 
        
        cv2.circle(desenhar, center_colonia, radius_colonia, cor, 2)
        total_desenhadas += 1
    
    # if colony_details_for_debug:
    #     logger.info(f"Debug - Detalhes das primeiras colônias classificadas: {colony_details_for_debug[:5]}")

    logger.info(f"[{nome_amostra}] Tempo para loop de marcadores e classificação: {time.time() - loop_marcadores_start_time:.4f}s")

    resumo_contagem = dict(Counter(classificacoes_cores))
    resumo_contagem['total'] = total_desenhadas # Usar total_desenhadas que é o que realmente foi aceito e circulado

    logger.info(f"[{nome_amostra}] Total avaliadas: {total_avaliadas}, Filtradas por área: {total_filtradas_area}, "
                f"Filtradas por circularidade: {total_filtradas_circularidade}, Desenhadas (final): {total_desenhadas}, "
                f"Contagem final (dict): {resumo_contagem}")
    
    logger.info(f"[{nome_amostra}] Tempo do núcleo de processamento: {time.time() - processing_core_start_time:.4f}s")

    # --- Lógica de Densidade e Estimativa CORRIGIDA ---
    total_contado_final = resumo_contagem.get('total', 0)
    area_pixel_r_margem = np.pi * (r_margem ** 2) 
    area_pixel_r_total_placa = np.pi * (r ** 2)    

    densidade_calculada_cm2 = 0
    estimativa_total_placa_calculada = total_contado_final # Padrão se não puder calcular densidade
    area_efetiva_amostrada_cm2 = 0

    if r_margem == r and AREA_PADRAO_PLACA_CM2 > 0: # Se amostramos 100% da área que corresponde a AREA_PADRAO_PLACA_CM2
        # Neste caso, a área amostrada é a área padrão da placa.
        area_efetiva_amostrada_cm2 = AREA_PADRAO_PLACA_CM2
        densidade_calculada_cm2 = round(total_contado_final / AREA_PADRAO_PLACA_CM2, 2)
        estimativa_total_placa_calculada = total_contado_final 
        logger.info(f"[{nome_amostra}] Cálculo de densidade: r_margem == r. Total: {total_contado_final}, Area Padrão: {AREA_PADRAO_PLACA_CM2}, Densidade: {densidade_calculada_cm2}")
    elif area_pixel_r_total_placa > 0 and AREA_PADRAO_PLACA_CM2 > 0 : # Caso geral onde r_margem < r
        fracao_area_amostrada_pixels = area_pixel_r_margem / area_pixel_r_total_placa
        area_efetiva_amostrada_cm2 = fracao_area_amostrada_pixels * AREA_PADRAO_PLACA_CM2
        
        if area_efetiva_amostrada_cm2 > 0:
            densidade_calculada_cm2 = round(total_contado_final / area_efetiva_amostrada_cm2, 2)
            estimativa_total_placa_calculada = round(densidade_calculada_cm2 * AREA_PADRAO_PLACA_CM2, 2)
            logger.info(f"[{nome_amostra}] Cálculo de densidade: r_margem < r. Total: {total_contado_final}, Area Amostrada cm2: {area_efetiva_amostrada_cm2:.2f}, Densidade: {densidade_calculada_cm2}, Estimativa: {estimativa_total_placa_calculada}")
        else: # area_efetiva_amostrada_cm2 é 0 (r_margem provavelmente é 0)
            logger.warning(f"[{nome_amostra}] area_efetiva_amostrada_cm2 é zero. Não é possível calcular densidade de forma usual.")
            # Se total_contado_final > 0, a densidade é tecnicamente infinita.
            # Mantemos densidade 0 e estimativa como o total contado.
            densidade_calculada_cm2 = 0 
            estimativa_total_placa_calculada = total_contado_final
    else: # area_pixel_r_total_placa é 0 (raio r é 0)
        logger.warning(f"[{nome_amostra}] area_pixel_r_total_placa é zero. Não é possível calcular densidade.")
        densidade_calculada_cm2 = 0
        estimativa_total_placa_calculada = total_contado_final
    # --- Fim da Lógica de Densidade ---


    hora_brasilia = datetime.now(timezone.utc) - timedelta(hours=3)
    texto_cabecalho = [
        f"{nome_amostra}",
        f"{hora_brasilia.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Total Contado: {total_contado_final} UFC", 
        f"Densidade: {densidade_calculada_cm2:.2f} UFC/cm^2", 
        f"Estimativa ({AREA_PADRAO_PLACA_CM2:.1f} cm^2): {estimativa_total_placa_calculada:.2f} UFC"
    ]
    
    altura_legenda = 22 * len(texto_cabecalho) + 20 
    # Ajustar largura da legenda se os textos ficarem muito compridos
    # Garantir que não ultrapasse a largura da imagem 'desenhar'
    largura_legenda_max = min(450, desenhar.shape[1] - 10) # Ex: 450px de largura ou um pouco menos que a imagem
    cv2.rectangle(desenhar, (5, 5), (largura_legenda_max, 5 + altura_legenda), (0, 0, 0), -1) 

    for i, linha in enumerate(texto_cabecalho):
        y_texto = 25 + i * 22
        cv2.putText(desenhar, linha, (10, y_texto), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

    encode_start_time = time.time()
    _, buffer = cv2.imencode('.jpg', desenhar)
    logger.info(f"[{nome_amostra}] Tempo para encodificar imagem: {time.time() - encode_start_time:.4f}s")

    feedback_headers = {
        "X-Resumo-Total": str(resumo_contagem.get('total',0)), # Adicionado para consistência com App.jsx
        "X-Resumo-Amarela": str(resumo_contagem.get('amarela',0)),
        "X-Resumo-Bege": str(resumo_contagem.get('bege',0)),
        "X-Resumo-Clara": str(resumo_contagem.get('clara',0)),
        "X-Resumo-Rosada": str(resumo_contagem.get('rosada',0)),
        "X-Feedback-Avaliadas": str(total_avaliadas),
        "X-Feedback-Filtradas-Area": str(total_filtradas_area),
        "X-Feedback-Filtradas-Circularidade": str(total_filtradas_circularidade),
        "X-Feedback-Desenhadas": str(total_desenhadas), 
        "X-Feedback-Raio-Detectado-Px": str(r), 
        "X-Feedback-Area-Amostrada-Cm2": f"{area_efetiva_amostrada_cm2:.2f}",
        "X-Feedback-Densidade-Colonias-Cm2": f"{densidade_calculada_cm2:.2f}",
        "X-Feedback-Estimativa-Total-Colonias": f"{estimativa_total_placa_calculada:.2f}"
    }
    
    logger.info(f"[{nome_amostra}] Processamento total da imagem levou: {time.time() - total_process_start_time:.4f}s")
    return resumo_contagem, BytesIO(buffer.tobytes()), feedback_headers

@app.post("/contar/", summary="Conta e classifica colônias em uma imagem")
async def contar_colonias_endpoint(
    file: UploadFile = File(..., description="Imagem da placa de Petri"),
    nome_amostra: str = Form(..., description="Identificação da amostra."),
    x: int = Form(None, description="Coord. X manual do centro da placa (pixels na imagem original)"),
    y: int = Form(None, description="Coord. Y manual do centro da placa (pixels na imagem original)"),
    r: int = Form(None, description="Raio manual da placa (pixels na imagem original)")
):
    conteudo_arquivo = await file.read()
    if not conteudo_arquivo:
        raise HTTPException(status_code=400, detail="Arquivo enviado está vazio.")

    try:
        resumo, imagem_processada, feedback_dict = processar_imagem(conteudo_arquivo, nome_amostra, x_manual=x, y_manual=y, r_manual=r)
        
        # Construir cabeçalhos de resposta
        # Os X-Resumo-* são derivados do dict resumo retornado por processar_imagem
        # Os X-Feedback-* são o dict feedback_dict retornado por processar_imagem
        response_headers = {}
        for k, v in resumo.items(): # Para total, amarela, bege, etc.
            # O frontend espera X-Resumo-TOTAL, X-Resumo-AMARELA, etc.
            # O feedback_dict já tem X-Resumo-Total, então não precisa adicionar aqui se estiver no feedback_dict
            if f"X-Resumo-{k.upper()}" not in feedback_dict: # Evitar duplicar se já estiver no feedback_dict
                 response_headers[f"X-Resumo-{k.upper()}"] = str(v)
        
        response_headers.update(feedback_dict) # Adiciona todos os X-Feedback e os X-Resumo do dict

        return StreamingResponse(imagem_processada, media_type="image/jpeg", headers=response_headers)

    except ValueError as e: 
        logger.error(f"Erro de valor durante o processamento para {nome_amostra}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException as e: 
        raise e
    except Exception as e: 
        logger.exception(f"Erro inesperado durante o processamento para {nome_amostra}") # .exception inclui stack trace
        raise HTTPException(status_code=500, detail=f"Erro interno no servidor ao processar a imagem.")
