from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import numpy as np
import cv2
from io import BytesIO
from collections import Counter
from datetime import datetime, timedelta, timezone
# import pandas as pd # Comentado pois não parece estar em uso ativo
import os
import logging
from scipy import ndimage
import time # Importe a biblioteca time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="API de Contagem de Colônias",
    description="Processa imagens de placas de Petri para contar e classificar colônias.",
    version="1.5.0" # Você pode atualizar a versão se desejar, ex: "1.5.1" ou "1.6.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://contadorbacterias.netlify.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-Resumo-Total", "X-Resumo-Amarela", "X-Resumo-Bege", "X-Resumo-Clara", "X-Resumo-Rosada",
        "X-Feedback-Avaliadas", "X-Feedback-Filtradas-Area", "X-Feedback-Filtradas-Circularidade",
        "X-Feedback-Desenhadas", "X-Feedback-Raio",
        "X-Feedback-Densidade-Colonias-Cm2",
        "X-Feedback-Estimativa-Total-Colonias"
    ]
)

AREA_PADRAO_PLACA_CM2 = 57.5
MAX_IMAGE_DIM = 1200 # Defina uma dimensão máxima para a imagem (ex: 1200 pixels)

def classificar_cor_hsv(hsv_color_mean):
    h, s, v = hsv_color_mean
    if s < 40 and v > 190:
        return 'clara'
    elif 20 <= h <= 35 and s > 60 and v > 60:
        return 'amarela'
    elif (0 <= h <= 15 or 160 <= h <= 179) and s > 60 and v > 60:
        return 'rosada'
    else:
        return 'bege'

def detectar_placa(img_gray):
    start_time = time.time()
    # Ajuste os parâmetros de HoughCircles se necessário, especialmente após o redimensionamento
    # Talvez minRadius precise ser menor se a imagem for significativamente reduzida.
    # Mantenha minDist alto para evitar detectar múltiplos círculos na mesma placa.
    # param1 e param2 podem precisar de ajuste fino.
    img_blur = cv2.medianBlur(img_gray, 5) # O desfoque mediano pode ajudar
    circulos = cv2.HoughCircles(img_blur, cv2.HOUGH_GRADIENT, dp=1.2, minDist=img_gray.shape[0]//4, # minDist relativo ao tamanho
                                 param1=50, param2=30, minRadius=int(img_gray.shape[0]*0.15), maxRadius=int(img_gray.shape[0]*0.5))

    logger.info(f"Tempo para cv2.HoughCircles: {time.time() - start_time:.4f}s")
    if circulos is not None:
        circulos = np.uint16(np.around(circulos))
        # Adicione uma verificação para garantir que apenas um círculo (o melhor) seja retornado se múltiplos forem detectados
        # Por exemplo, o maior ou o mais central, dependendo do caso.
        # Aqui, estamos apenas pegando o primeiro detectado, como antes.
        logger.info(f"Placa detectada com centro em ({circulos[0][0][0]}, {circulos[0][0][1]}) e raio {circulos[0][0][2]}")
        return circulos[0][0]
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
        raise HTTPException(status_code=400, detail="Não foi possível decodificar a imagem.")

    # Redimensionamento da Imagem
    resize_start_time = time.time()
    altura_orig, largura_orig = img_original.shape[:2]
    img = img_original.copy() # Trabalhar com uma cópia para manter a original se necessário

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
        # Se coordenadas manuais são fornecidas, elas provavelmente são para a imagem original.
        # Precisamos reescalar essas coordenadas para a imagem redimensionada.
        fator_escala_largura = img.shape[1] / largura_orig
        fator_escala_altura = img.shape[0] / altura_orig
        # Usar uma média dos fatores ou o menor deles para o raio para ser conservador
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

    # Demais processamentos (máscara, limiarização, watershed, etc.)
    # Essas etapas agora operam na imagem 'img' (potencialmente redimensionada)
    processing_core_start_time = time.time()

    r_margem = int(r * 0.90) # Margem dentro do raio detectado/reescalado
    mask_placa = np.zeros(gray.shape, dtype=np.uint8)
    cv2.circle(mask_placa, (x, y), r_margem, 255, -1)
    
    img_masked = cv2.bitwise_and(img, img, mask=mask_placa)
    gray_masked = cv2.bitwise_and(gray, gray, mask=mask_placa) # Usar 'gray' que é da imagem redimensionada
    
    gray_eq = cv2.equalizeHist(gray_masked)
    blurred = cv2.GaussianBlur(gray_eq, (5, 5), 0)

    thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY_INV, 41, 4) # Os parâmetros aqui podem precisar de ajuste para imagens menores
    
    # Morfologia e Watershed
    # Os tamanhos dos elementos estruturantes e filtros podem ser sensíveis à escala da imagem
    opened = cv2.morphologyEx(thresh, cv2.MORPH_OPEN,
                               cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))) # (3,3) ou (5,5)
    dist_transform = cv2.distanceTransform(opened, cv2.DIST_L2, 5)
    
    # O 'size' do maximum_filter pode precisar ser ajustado com base no tamanho esperado das colônias na imagem redimensionada.
    # Se as colônias ficarem muito pequenas, um 'size' grande pode fundi-las.
    # Se ficarem grandes, um 'size' pequeno pode criar múltiplos centróides por colônia.
    local_max_filter_size = max(5, int(r_margem / 50)) # Exemplo de ajuste dinâmico, pode precisar de experimentação
    logger.info(f"[{nome_amostra}] Usando local_max_filter_size: {local_max_filter_size}")

    local_max = ndimage.maximum_filter(dist_transform, size=local_max_filter_size) == dist_transform # Era size=10
    
    markers, num_features = ndimage.label(local_max) # 'num_features' é o número de marcadores iniciais
    logger.info(f"[{nome_amostra}] Número inicial de marcadores (num_features): {num_features}")

    markers = markers + 1 # Background é 1, objetos > 1
    unknown = cv2.subtract(opened, np.uint8(local_max * 255)) # Multiplicar local_max por 255 para criar a máscara binária
    markers[unknown == 255] = 0 # Regiões desconhecidas
    
    watershed_start_time = time.time()
    markers = cv2.watershed(img_masked, markers.astype(np.int32))
    logger.info(f"[{nome_amostra}] Tempo para cv2.watershed: {time.time() - watershed_start_time:.4f}s")

    classificacoes_cores = []
    total_avaliadas = 0
    total_filtradas_area = 0
    total_filtradas_circularidade = 0
    total_desenhadas = 0
    
    # Os limiares de área (area_min, area_max) podem precisar ser ajustados
    # se a imagem for redimensionada. Eles devem ser relativos à nova escala.
    # Exemplo: Se antes era 10-800 pixels na imagem original, e a imagem foi reduzida pela metade (fator 0.5),
    # a nova área seria (10 * 0.5^2) a (800 * 0.5^2) = 2.5 a 200.
    # É mais fácil pensar em termos de diâmetro da colônia.
    # Se uma colônia tinha 5 pixels de raio na original, e a imagem é reduzida por MAX_IMAGE_DIM/largura_orig,
    # o novo raio será 5 * (MAX_IMAGE_DIM/largura_orig). A área = pi*r^2.
    
    # Calcular um fator de escala de área para ajustar os limiares
    fator_escala_area = (img.shape[0] * img.shape[1]) / (largura_orig * altura_orig)
    
    # Limites de área ajustados (EXEMPLO, você precisará encontrar valores bons)
    # Estes valores devem ser baseados no tamanho esperado das colônias APÓS o redimensionamento.
    # Se MAX_IMAGE_DIM = 1200, e a imagem original era 4000x3000, o redimensionamento é para 1200x900.
    # Fator de redução linear ~1/3. Fator de área ~1/9.
    # Se antes o limite mínimo era 10 pixels, agora poderia ser ~1 pixel.
    # Se o máximo era 800, agora ~80-90 pixels.
    # É crucial testar isso.
    AREA_MIN_COLONIA = max(1.0, 10.0 * fator_escala_area) # Ajuste com base na observação
    AREA_MAX_COLONIA = min(800.0 * fator_escala_area, (np.pi * (r_margem * 0.2)**2) ) # Não maior que 20% do raio da placa
    CIRCULARIDADE_MIN = 0.35 # Manter, pois é uma razão

    logger.info(f"[{nome_amostra}] Usando AREA_MIN_COLONIA: {AREA_MIN_COLONIA:.2f}, AREA_MAX_COLONIA: {AREA_MAX_COLONIA:.2f} (fator_escala_area: {fator_escala_area:.3f})")

    loop_marcadores_start_time = time.time()
    for marker_val in np.unique(markers):
        if marker_val <= 1: # Background (0 de unknown, 1 de markers=markers+1) ou -1 (bordas do watershed)
            continue
        
        mask = np.zeros(gray.shape, dtype=np.uint8)
        mask[markers == marker_val] = 255
        
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        
        cnt = max(contours, key=cv2.contourArea) # Pegar o maior contorno se houver múltiplos para um marcador
        area = cv2.contourArea(cnt)
        total_avaliadas += 1

        if area < AREA_MIN_COLONIA or area > AREA_MAX_COLONIA:
            total_filtradas_area += 1
            continue

        perimeter = cv2.arcLength(cnt, True)
        if perimeter == 0: # Evitar divisão por zero
            continue
        circularity = 4 * np.pi * (area / (perimeter * perimeter))
        if circularity < CIRCULARIDADE_MIN:
            total_filtradas_circularidade += 1
            continue

        (cx, cy), radius_colonia = cv2.minEnclosingCircle(cnt)
        center_colonia = (int(cx), int(cy))
        radius_colonia = int(radius_colonia)

        # Verificar se o centro da colônia está dentro da margem da placa de Petri
        if np.linalg.norm(np.array(center_colonia) - np.array((x, y))) > r_margem - radius_colonia: # Subtrai o raio da colônia
            continue                                                                              # para evitar cortar colônias na borda

        mean_color_bgr = cv2.mean(img, mask=mask)[:3] # Usar 'img' que é a imagem original ou redimensionada
        hsv_pixel = cv2.cvtColor(np.uint8([[mean_color_bgr]]), cv2.COLOR_BGR2HSV)
        tipo = classificar_cor_hsv(hsv_pixel[0][0])
        classificacoes_cores.append(tipo)

        # Não desenhar colônias excessivamente grandes (artefatos)
        if radius_colonia > (r_margem * 0.25): # Se o raio da colônia for >25% do raio da placa, provavelmente é um erro.
             # logger.info(f"Colônia grande filtrada (raio {radius_colonia} > {r_margem*0.25})")
             continue

        cor = (0, 0, 255) # Vermelho padrão para 'bege'
        if tipo == 'amarela':
            cor = (0, 255, 255) # Amarelo
        elif tipo == 'rosada':
            cor = (203, 192, 255) # Rosa claro
        elif tipo == 'clara':
            cor = (255, 255, 255) # Branco
        
        cv2.circle(desenhar, center_colonia, radius_colonia, cor, 2)
        # cv2.putText(desenhar, str(int(area)), (center_colonia[0], center_colonia[1]-radius_colonia-5), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (200,200,200),1)
        total_desenhadas += 1
    
    logger.info(f"[{nome_amostra}] Tempo para loop de marcadores e classificação: {time.time() - loop_marcadores_start_time:.4f}s")

    resumo_contagem = dict(Counter(classificacoes_cores))
    resumo_contagem['total'] = len(classificacoes_cores) # Deve ser o número de colônias que passaram por todos os filtros

    logger.info(f"[{nome_amostra}] Total avaliadas: {total_avaliadas}, Filtradas por área: {total_filtradas_area}, "
                f"Filtradas por circularidade: {total_filtradas_circularidade}, Desenhadas (final): {total_desenhadas}, "
                f"Contagem final (dict): {resumo_contagem}")
    
    logger.info(f"[{nome_amostra}] Tempo do núcleo de processamento: {time.time() - processing_core_start_time:.4f}s")

    # Cálculos de densidade e estimativa
    # A AREA_PADRAO_PLACA_CM2 é a área real da placa em cm2.
    # O raio 'r_margem' está em pixels na imagem (potencialmente redimensionada).
    # Precisamos de um fator de conversão pixel -> cm se quisermos calcular a área amostrada em cm2
    # Se não temos uma referência física (ex: diâmetro da placa em pixels), é difícil obter cm2 exato.
    # Assumimos que 'r_margem' na imagem representa a parte da placa com área AREA_PADRAO_PLACA_CM2.
    # Esta é uma simplificação. Para ser preciso, seria necessário calibrar (ex: saber quantos cm um pixel representa).
    
    area_pixel_placa_amostrada = np.pi * (r_margem ** 2) # Área em pixels^2 da região analisada (círculo com r_margem)
    
    # Se a contagem é feita na imagem redimensionada, mas a densidade deve refletir a placa original:
    # O número de colônias contadas (resumo_contagem['total']) é da imagem processada.
    # Se a área da placa (AREA_PADRAO_PLACA_CM2) é uma constante, então a densidade é
    # UFC / AREA_PADRAO_PLACA_CM2.
    # Mas, se r_margem é usado para estimar a área amostrada, e r_margem vem da imagem redimensionada,
    # a densidade calculada (UFC / area_pixel_placa_amostrada) seria em UFC/pixel^2.
    # Para converter para UFC/cm^2, precisaríamos do fator de conversão (pixels/cm)^2.
    
    # Vamos manter a lógica anterior, mas cientes de que 'r_margem' agora é da imagem redimensionada.
    # O ideal seria ter o raio REAL da placa em cm, e o raio da placa em pixels NA IMAGEM ORIGINAL.
    # Isso daria um fator pixel/cm. E então aplicar esse fator.

    # Por ora, vamos assumir que o processamento, mesmo em imagem redimensionada, visa contar
    # todas as colônias que estariam na área padrão.
    # Se r_margem é o raio da área efetivamente analisada na imagem (redimensionada ou não)
    # E essa área corresponde a uma porção da placa real.
    
    # A lógica original usava AREA_PADRAO_PLACA_CM2 / area_pixel_placa para um fator.
    # Isso implica que area_pixel_placa é a área total da placa em pixels.
    # Se 'r' (raio detectado) é o raio da placa inteira em pixels (na imagem processada), então:
    area_total_placa_pixels = np.pi * (r ** 2) # Raio da placa detectada na imagem processada
    
    # Se a AREA_PADRAO_PLACA_CM2 corresponde a area_total_placa_pixels
    densidade = round(resumo_contagem['total'] / AREA_PADRAO_PLACA_CM2, 2) if AREA_PADRAO_PLACA_CM2 > 0 else 0
    # Esta densidade seria UFC/cm^2, assumindo que 'total' é o número de colônias na área padrão.
    # No entanto, se 'total' é apenas da área dentro de r_margem, e r_margem < r:
    if area_total_placa_pixels > 0:
        area_amostrada_cm2 = (area_pixel_placa_amostrada / area_total_placa_pixels) * AREA_PADRAO_PLACA_CM2
        densidade_na_amostra = round(resumo_contagem['total'] / area_amostrada_cm2, 2) if area_amostrada_cm2 > 0 else 0
    else:
        area_amostrada_cm2 = 0
        densidade_na_amostra = 0

    # Estimativa para a placa inteira, usando a densidade calculada na área amostrada
    estimativa_total_na_placa = round(densidade_na_amostra * AREA_PADRAO_PLACA_CM2, 2)


    # Informações para cabeçalho
    hora_brasilia = datetime.now(timezone.utc) - timedelta(hours=3)
    texto_cabecalho = [
        f"{nome_amostra}",
        f"{hora_brasilia.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Total Contado: {resumo_contagem.get('total', 0)} UFC", # Usar .get para segurança
        f"Densidade (amostra): {densidade_na_amostra:.2f} UFC/cm^2",
        f"Estimativa (placa {AREA_PADRAO_PLACA_CM2} cm^2): {estimativa_total_na_placa:.2f} UFC"
    ]
    # ... (código para desenhar texto no cabeçalho da imagem) ...
    # Fundo da legenda
    altura_legenda = 22 * len(texto_cabecalho) + 20 # Aumentar um pouco a altura por linha
    cv2.rectangle(desenhar, (5, 5), (400, 5 + altura_legenda), (0, 0, 0), -1) # Aumentar largura se necessário

    for i, linha in enumerate(texto_cabecalho):
        y_texto = 25 + i * 22
        cv2.putText(desenhar, linha, (10, y_texto), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)


    encode_start_time = time.time()
    _, buffer = cv2.imencode('.jpg', desenhar)
    logger.info(f"[{nome_amostra}] Tempo para encodificar imagem: {time.time() - encode_start_time:.4f}s")

    feedback_headers = {
        "X-Feedback-Avaliadas": str(total_avaliadas),
        "X-Feedback-Filtradas-Area": str(total_filtradas_area),
        "X-Feedback-Filtradas-Circularidade": str(total_filtradas_circularidade),
        "X-Feedback-Desenhadas": str(total_desenhadas), # Renomeado para refletir contagem final desenhada
        "X-Feedback-Raio-Detectado-Px": str(r), # Raio da placa na imagem processada
        "X-Feedback-Area-Amostrada-Cm2": f"{area_amostrada_cm2:.2f}",
        "X-Feedback-Densidade-Colonias-Cm2": f"{densidade_na_amostra:.2f}",
        "X-Feedback-Estimativa-Total-Colonias": f"{estimativa_total_na_placa:.2f}"
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
        resumo, imagem_processada, feedback = processar_imagem(conteudo_arquivo, nome_amostra, x_manual=x, y_manual=y, r_manual=r)
        headers = {f"X-Resumo-{k.capitalize()}": str(v) for k, v in resumo.items()}
        headers.update(feedback)
        return StreamingResponse(imagem_processada, media_type="image/jpeg", headers=headers)
    except ValueError as e: # Capturar erros de decodificação ou outros ValueErrors
        logger.error(f"Erro de valor durante o processamento para {nome_amostra}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException as e: # Re-lançar HTTPExceptions para que o FastAPI as manipule
        raise e
    except Exception as e: # Capturar qualquer outra exceção inesperada
        logger.exception(f"Erro inesperado durante o processamento para {nome_amostra}: {str(e)}") # .exception inclui stack trace
        raise HTTPException(status_code=500, detail=f"Erro interno no servidor ao processar a imagem: {str(e)}")
