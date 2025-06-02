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
    version="1.6.1"  # Versão incrementada para refletir as mudanças
)

# Configuração do CORS para permitir o acesso do seu frontend Netlify
# Adicione outras origens se estiver testando de locais diferentes (ex: http://localhost:xxxx)
ALLOWED_ORIGINS = [
    "https://contadorbacterias.netlify.app",
    # "http://localhost:5173", # Exemplo para teste local com Vite na porta padrão
    # Adicione a URL do seu ambiente de desenvolvimento local se for diferente
]


app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS, 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[ # Cabeçalhos que o frontend poderá ler
        "X-Resumo-Total", "X-Resumo-Amarela", "X-Resumo-Bege", "X-Resumo-Clara", "X-Resumo-Rosada",
        "X-Feedback-Avaliadas", "X-Feedback-Filtradas-Area", "X-Feedback-Filtradas-Circularidade",
        "X-Feedback-Desenhadas", "X-Feedback-Raio-Detectado-Px",
        "X-Feedback-Area-Amostrada-Cm2", 
        "X-Feedback-Densidade-Colonias-Cm2", 
        "X-Feedback-Estimativa-Total-Colonias"
    ]
)

AREA_PADRAO_PLACA_CM2 = 57.5  # Área padrão de uma placa de Petri em cm²
MAX_IMAGE_DIM = 1200          # Dimensão máxima para redimensionamento da imagem

def classificar_cor_hsv(hsv_color_mean):
    h, s, v = hsv_color_mean
    # Ajustes iniciais nos ranges - você precisará refinar com base em suas amostras!
    if s < 45 and v > 180: 
        return 'clara'
    elif 18 <= h <= 38 and s > 50 and v > 50: 
        return 'amarela'
    elif (0 <= h <= 18 or 155 <= h <= 179) and s > 50 and v > 50: 
        return 'rosada'
    else:
        return 'bege'

def detectar_placa(img_gray):
    detection_start_time = time.time()
    img_blur = cv2.medianBlur(img_gray, 5) 
    
    min_dim_img = min(img_gray.shape[0], img_gray.shape[1])
    min_radius_hough = int(min_dim_img * 0.15) 
    max_radius_hough = int(min_dim_img * 0.50) 
    min_dist_hough = min_dim_img // 2 

    circulos = cv2.HoughCircles(img_blur, cv2.HOUGH_GRADIENT, dp=1.2, minDist=min_dist_hough,
                                 param1=50, param2=30, minRadius=min_radius_hough, maxRadius=max_radius_hough)

    logger.info(f"Tempo para cv2.HoughCircles: {time.time() - detection_start_time:.4f}s. Parâmetros: minDist={min_dist_hough}, param2=30, minR={min_radius_hough}, maxR={max_radius_hough}")
    
    if circulos is not None:
        circulos = np.uint16(np.around(circulos))
        # Se múltiplos círculos são detectados, idealmente escolher o "melhor"
        # (ex: o de maior raio, ou o mais central). Por simplicidade, pegamos o primeiro.
        best_circle = circulos[0][0] 
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
        raise ValueError("Não foi possível decodificar a imagem.")

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
        logger.info(f"[{nome_amostra}] Imagem ({largura_orig}x{altura_orig}) não requer redimensionamento (MAX_DIM: {MAX_IMAGE_DIM}).")
    logger.info(f"[{nome_amostra}] Tempo para redimensionar: {time.time() - resize_start_time:.4f}s")

    desenhar = img.copy()
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    placa_detection_start_time = time.time()
    if x_manual is not None and y_manual is not None and r_manual is not None:
        # Reescalar coordenadas manuais se a imagem foi redimensionada
        fator_escala_largura = img.shape[1] / largura_orig
        fator_escala_altura = img.shape[0] / altura_orig
        fator_escala_raio = min(fator_escala_largura, fator_escala_altura) # Usar o menor fator para o raio

        x = int(x_manual * fator_escala_largura)
        y = int(y_manual * fator_escala_altura)
        r = int(r_manual * fator_escala_raio)
        logger.info(f"[{nome_amostra}] Usando parâmetros manuais reescalados para a placa: ({x}, {y}, {r})")
    else:
        circulo = detectar_placa(gray)
        if circulo is None:
            logger.warning(f"[{nome_amostra}] Não foi possível detectar a placa automaticamente.")
            raise HTTPException(status_code=422, detail="Placa de Petri não detectada automaticamente.")
        x, y, r = circulo
    logger.info(f"[{nome_amostra}] Tempo para detecção da placa: {time.time() - placa_detection_start_time:.4f}s")
    
    if r == 0: 
        logger.error(f"[{nome_amostra}] Raio da placa detectado como zero.")
        raise HTTPException(status_code=422, detail="Raio da placa (r) é zero.")

    # Início do processamento principal da imagem
    core_processing_start_time = time.time()

    r_margem = int(r * 0.90) # Área de contagem é 90% do raio detectado
    mask_placa = np.zeros(gray.shape, dtype=np.uint8)
    cv2.circle(mask_placa, (x, y), r_margem, 255, -1)
    
    img_masked = cv2.bitwise_and(img, img, mask=mask_placa)
    gray_masked = cv2.bitwise_and(gray, gray, mask=mask_placa) 
    
    gray_eq = cv2.equalizeHist(gray_masked)
    blurred = cv2.GaussianBlur(gray_eq, (5, 5), 0) 

    thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY_INV, 41, 4) 
    
    opened = cv2.morphologyEx(thresh, cv2.MORPH_OPEN,
                               cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3,3))) 
    dist_transform = cv2.distanceTransform(opened, cv2.DIST_L2, 5)
    
    # Ajuste do local_max_filter_size:
    # Um valor menor pode ajudar a separar colônias próximas ou detectar as menores.
    # Testar valores ímpares. 7 é um chute inicial.
    local_max_filter_size = 7 
    logger.info(f"[{nome_amostra}] Usando local_max_filter_size: {local_max_filter_size}")

    local_max = ndimage.maximum_filter(dist_transform, size=local_max_filter_size) == dist_transform
    
    markers, num_features = ndimage.label(local_max) 
    logger.info(f"[{nome_amostra}] Número inicial de marcadores (picos locais): {num_features}")

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
        
    # Ajuste dos limites de área e circularidade
    AREA_MIN_COLONIA = 4.0  # Teste inicial, aumente se pegar muito ruído, diminua se perder colônias pequenas
    AREA_MAX_COLONIA_FATOR = 0.05 # Colônias não devem ter área maior que 5% da área da placa (r_margem)
    AREA_MAX_COLONIA = np.pi * (r_margem**2) * AREA_MAX_COLONIA_FATOR 
    CIRCULARIDADE_MIN = 0.30 # Mais permissivo

    logger.info(f"[{nome_amostra}] Limites de filtro: AREA_MIN={AREA_MIN_COLONIA:.2f}, AREA_MAX={AREA_MAX_COLONIA:.2f}, CIRC_MIN={CIRCULARIDADE_MIN:.2f}")

    loop_marcadores_start_time = time.time()
    for marker_val in np.unique(markers):
        if marker_val <= 1: # Ignorar background e bordas do watershed
            continue
        
        mask_colonia = np.zeros(gray.shape, dtype=np.uint8)
        mask_colonia[markers == marker_val] = 255
        
        contours, _ = cv2.findContours(mask_colonia, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        
        cnt = max(contours, key=cv2.contourArea) 
        area = cv2.contourArea(cnt)
        total_avaliadas += 1

        if area < AREA_MIN_COLONIA or area > AREA_MAX_COLONIA:
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

        # Verificar se o centro da colônia está dentro da margem da placa (r_margem)
        if np.linalg.norm(np.array(center_colonia) - np.array((x, y))) > r_margem : 
            continue                                                                            

        mean_color_bgr = cv2.mean(img, mask=mask_colonia)[:3] 
        hsv_pixel = cv2.cvtColor(np.uint8([[mean_color_bgr]]), cv2.COLOR_BGR2HSV)
        tipo = classificar_cor_hsv(hsv_pixel[0][0])
        classificacoes_cores.append(tipo)
        
        # Evitar desenhar círculos de colônias excessivamente grandes (provavelmente artefatos)
        if radius_colonia > (r_margem * 0.2): # Se o raio da colônia for >20% do r_margem
             continue

        cor_desenho = (0, 0, 255) # Padrão 'bege'
        if tipo == 'amarela': cor_desenho = (0, 255, 255) 
        elif tipo == 'rosada': cor_desenho = (203, 192, 255) 
        elif tipo == 'clara': cor_desenho = (255, 255, 255) 
        
        cv2.circle(desenhar, center_colonia, int(radius_colonia), cor_desenho, 2) # Usar int() para raio
        total_desenhadas += 1
    
    logger.info(f"[{nome_amostra}] Tempo para loop de marcadores e classificação: {time.time() - loop_marcadores_start_time:.4f}s")

    resumo_contagem = dict(Counter(classificacoes_cores))
    resumo_contagem['total'] = total_desenhadas # Total é o que foi efetivamente desenhado/aceito

    logger.info(f"[{nome_amostra}] Resultados da contagem: Avaliadas={total_avaliadas}, Filtradas Área={total_filtradas_area}, "
                f"Filtradas Circ.={total_filtradas_circularidade}, Desenhadas/Total Final={total_desenhadas}. Detalhe cores: {resumo_contagem}")
    logger.info(f"[{nome_amostra}] Tempo do núcleo de processamento (segmentação e filtros): {time.time() - core_processing_start_time:.4f}s")

    # --- Lógica de Densidade e Estimativa SIMPLIFICADA ---
    # Assume que 'total_desenhadas' é a contagem para a placa inteira de AREA_PADRAO_PLACA_CM2
    total_contado_final = resumo_contagem.get('total', 0)
    densidade_calculada_cm2 = 0
    estimativa_total_placa_calculada = total_contado_final 
    area_efetiva_amostrada_cm2_reportada = AREA_PADRAO_PLACA_CM2 # Reportar a área padrão como a área amostrada nesta lógica

    if AREA_PADRAO_PLACA_CM2 > 0:
        densidade_calculada_cm2 = round(total_contado_final / AREA_PADRAO_PLACA_CM2, 2)
        # A estimativa é a própria contagem, pois assumimos que o total_contado_final
        # já se refere à área padrão da placa.
    else: # Caso AREA_PADRAO_PLACA_CM2 seja 0 ou inválida
        logger.warning(f"[{nome_amostra}] AREA_PADRAO_PLACA_CM2 é zero ou inválida. Densidade não pode ser calculada.")
        area_efetiva_amostrada_cm2_reportada = 0
        
    logger.info(f"[{nome_amostra}] Cálculo de densidade simplificado: Total Contado={total_contado_final}, "
                f"Area Padrão Placa={AREA_PADRAO_PLACA_CM2}cm², Densidade Calculada={densidade_calculada_cm2} UFC/cm², "
                f"Estimativa Placa={estimativa_total_placa_calculada} UFC")
    # --- Fim da Lógica de Densidade Simplificada ---

    hora_brasilia = datetime.now(timezone.utc) - timedelta(hours=3)
    texto_cabecalho = [
        f"{nome_amostra}",
        f"{hora_brasilia.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Total Contado: {total_contado_final} UFC", 
        f"Densidade: {densidade_calculada_cm2:.2f} UFC/cm^2", 
        f"Estimativa ({AREA_PADRAO_PLACA_CM2:.1f} cm^2): {estimativa_total_placa_calculada} UFC" # Sem arredondar aqui, já é int
    ]
    
    altura_legenda = 22 * len(texto_cabecalho) + 20 
    largura_legenda_max = min(480, desenhar.shape[1] - 10) 
    cv2.rectangle(desenhar, (5, 5), (largura_legenda_max, 5 + altura_legenda), (0, 0, 0), -1) 

    for i, linha in enumerate(texto_cabecalho):
        y_texto = 25 + i * 22
        cv2.putText(desenhar, linha, (10, y_texto), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

    encode_start_time = time.time()
    _, buffer = cv2.imencode('.jpg', desenhar)
    logger.info(f"[{nome_amostra}] Tempo para encodificar imagem: {time.time() - encode_start_time:.4f}s")

    feedback_headers = {
        "X-Resumo-Total": str(resumo_contagem.get('total',0)),
        "X-Resumo-Amarela": str(resumo_contagem.get('amarela',0)),
        "X-Resumo-Bege": str(resumo_contagem.get('bege',0)),
        "X-Resumo-Clara": str(resumo_contagem.get('clara',0)),
        "X-Resumo-Rosada": str(resumo_contagem.get('rosada',0)),
        "X-Feedback-Avaliadas": str(total_avaliadas),
        "X-Feedback-Filtradas-Area": str(total_filtradas_area),
        "X-Feedback-Filtradas-Circularidade": str(total_filtradas_circularidade),
        "X-Feedback-Desenhadas": str(total_desenhadas), 
        "X-Feedback-Raio-Detectado-Px": str(r), 
        "X-Feedback-Area-Amostrada-Cm2": f"{area_efetiva_amostrada_cm2_reportada:.2f}", # Reporta a área padrão
        "X-Feedback-Densidade-Colonias-Cm2": f"{densidade_calculada_cm2:.2f}",
        "X-Feedback-Estimativa-Total-Colonias": f"{estimativa_total_placa_calculada}" # Reporta o total contado
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
        
        # Os headers são construídos diretamente a partir do feedback_dict que já contém tudo formatado
        response_headers = feedback_dict

        return StreamingResponse(imagem_processada, media_type="image/jpeg", headers=response_headers)

    except ValueError as e: # Erros como falha na decodificação
        logger.error(f"Erro de valor (ex: decodificação) para {nome_amostra}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException as e: # Re-lançar HTTPExceptions específicas já levantadas
        logger.warning(f"HTTPException para {nome_amostra}: {e.detail} (Status: {e.status_code})")
        raise e
    except Exception as e: # Capturar qualquer outra exceção inesperada
        logger.exception(f"Erro interno inesperado durante o processamento para {nome_amostra}")
        raise HTTPException(status_code=500, detail=f"Erro interno no servidor. Tente novamente mais tarde.")
