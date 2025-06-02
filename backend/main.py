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
    version="1.6.3"  # Versão incrementada devido aos refinamentos
)

# Adicione a URL do seu ambiente de desenvolvimento local do Vite se necessário
ALLOWED_ORIGINS = [
    "https://contadorbacterias.netlify.app",
    # "http://localhost:5173", # Exemplo para Vite
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-Resumo-Total", "X-Resumo-Amarela", "X-Resumo-Bege", "X-Resumo-Clara", "X-Resumo-Rosada",
        "X-Feedback-Avaliadas", "X-Feedback-Filtradas-Area", "X-Feedback-Filtradas-Circularidade",
        "X-Feedback-Desenhadas", "X-Feedback-Raio-Detectado-Px",
        "X-Feedback-Area-Amostrada-Cm2",
        "X-Feedback-Densidade-Colonias-Cm2",
        "X-Feedback-Estimativa-Total-Colonias",
        "X-Feedback-Filtradas-Tamanho-Maximo" # Novo header de feedback
    ]
)

AREA_PADRAO_PLACA_CM2 = 57.5
MAX_IMAGE_DIM = 1200
# Constante para o limiar mínimo do perímetro para cálculo de circularidade
MIN_PERIMETER_THRESHOLD = 5.0
# Fator para filtro de colônias muito grandes. Considerar tornar configurável no futuro.
MAX_COLONY_RADIUS_FACTOR_OF_PETRI_MARGIN = 0.2

def classificar_cor_hsv(hsv_color_mean):
    h, s, v = hsv_color_mean
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
        fator_escala_largura = img.shape[1] / largura_orig
        fator_escala_altura = img.shape[0] / altura_orig
        fator_escala_raio = min(fator_escala_largura, fator_escala_altura) # Usar o menor fator para o raio para ser conservador
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

    if r == 0: # Checagem crucial
        logger.error(f"[{nome_amostra}] Raio da placa (r) é zero, impossível prosseguir.")
        raise HTTPException(status_code=422, detail="Raio da placa (r) é zero.")

    core_processing_start_time = time.time()
    r_margem = int(r * 0.90) # Raio da subárea efetivamente analisada
    mask_placa = np.zeros(gray.shape, dtype=np.uint8)
    cv2.circle(mask_placa, (x, y), r_margem, 255, -1)
    img_masked = cv2.bitwise_and(img, img, mask=mask_placa)
    gray_masked = cv2.bitwise_and(gray, gray, mask=mask_placa)
    gray_eq = cv2.equalizeHist(gray_masked) # Aplicar apenas na área de interesse
    blurred = cv2.GaussianBlur(gray_eq, (5, 5), 0)
    thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY_INV, 41, 4) # Parâmetros podem precisar de ajuste fino
    opened = cv2.morphologyEx(thresh, cv2.MORPH_OPEN,
                               cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3,3)))
    dist_transform = cv2.distanceTransform(opened, cv2.DIST_L2, 5)
    local_max_filter_size = 7 # Tamanho do filtro para encontrar picos locais
    logger.info(f"[{nome_amostra}] Usando local_max_filter_size: {local_max_filter_size}")
    local_max = ndimage.maximum_filter(dist_transform, size=local_max_filter_size) == dist_transform
    markers, num_features = ndimage.label(local_max)
    logger.info(f"[{nome_amostra}] Número inicial de marcadores (picos locais): {num_features}")
    markers = markers + 1 # Garante que o fundo (se houver) seja 1.
    unknown = cv2.subtract(opened, np.uint8(local_max * 255)) # Regiões incertas
    markers[unknown == 255] = 0 # Marcar regiões incertas para o watershed
    watershed_start_time = time.time()
    markers = cv2.watershed(img_masked, markers.astype(np.int32)) # Watershed na imagem colorida mascarada
    logger.info(f"[{nome_amostra}] Tempo para cv2.watershed: {time.time() - watershed_start_time:.4f}s")

    classificacoes_cores = []
    total_avaliadas = 0
    total_filtradas_area = 0
    total_filtradas_circularidade = 0
    total_filtradas_tamanho_maximo = 0 # Novo contador para colônias muito grandes
    total_desenhadas = 0

    AREA_MIN_COLONIA = 4.0 # Em pixels. Ajustar conforme a resolução típica das colônias.
    AREA_MAX_COLONIA_FATOR = 0.05 # Fração da área da placa (r_margem)
    AREA_MAX_COLONIA = np.pi * (r_margem**2) * AREA_MAX_COLONIA_FATOR # Área máxima em pixels
    CIRCULARIDADE_MIN = 0.30 # Ajustar conforme a forma esperada das colônias
    
    logger.info(f"[{nome_amostra}] Limites de filtro: AREA_MIN={AREA_MIN_COLONIA:.2f}px, AREA_MAX={AREA_MAX_COLONIA:.2f}px, CIRC_MIN={CIRCULARIDADE_MIN:.2f}, PERIM_MIN={MIN_PERIMETER_THRESHOLD:.2f}px")

    loop_marcadores_start_time = time.time()
    for marker_val in np.unique(markers):
        if marker_val <= 1: # Ignorar fundo (0 ou 1, dependendo da implementação do watershed) e bordas watershed (-1)
            continue
        
        mask_colonia = np.zeros(gray.shape, dtype=np.uint8)
        mask_colonia[markers == marker_val] = 255
        
        contours, _ = cv2.findContours(mask_colonia, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        
        cnt = max(contours, key=cv2.contourArea) # Usar o maior contorno se houver múltiplos para um marcador
        area = cv2.contourArea(cnt)
        total_avaliadas += 1

        if area < AREA_MIN_COLONIA or area > AREA_MAX_COLONIA:
            # Log detalhado para filtro de área
            if area < AREA_MIN_COLONIA:
                logger.debug(f"[{nome_amostra}] Colônia filtrada por área mínima: {area:.2f}px (limite: {AREA_MIN_COLONIA:.2f}px)")
            else:
                logger.debug(f"[{nome_amostra}] Colônia filtrada por área máxima: {area:.2f}px (limite: {AREA_MAX_COLONIA:.2f}px)")
            total_filtradas_area += 1
            continue
            
        perimeter = cv2.arcLength(cnt, True)
        # PONTO 5: Adicionar verificação de perímetro mínimo
        if perimeter < MIN_PERIMETER_THRESHOLD:
            logger.debug(f"[{nome_amostra}] Colônia filtrada por perímetro mínimo: {perimeter:.2f}px (limite: {MIN_PERIMETER_THRESHOLD:.2f}px)")
            total_filtradas_circularidade += 1 # Pode ser contado como circularidade ou um novo tipo de filtro
            continue
            
        circularity = 4 * np.pi * (area / (perimeter * perimeter))
        if circularity < CIRCULARIDADE_MIN:
            logger.debug(f"[{nome_amostra}] Colônia filtrada por circularidade: {circularity:.2f} (limite: {CIRCULARIDADE_MIN:.2f})")
            total_filtradas_circularidade += 1
            continue
            
        (cx, cy), radius_colonia = cv2.minEnclosingCircle(cnt)
        center_colonia = (int(cx), int(cy))
        radius_colonia_float = radius_colonia # Manter a precisão float para o filtro
        radius_colonia_int = int(radius_colonia_float) # Para desenhar

        # PONTO 3 (Manter): Verificação se o centro da colônia está dentro da área de margem.
        # Isso é uma salvaguarda, pois o watershed já operou em img_masked.
        # Contudo, o minEnclosingCircle pode ter seu centro ligeiramente fora se a colônia estiver na borda.
        if np.linalg.norm(np.array(center_colonia) - np.array((x, y))) > r_margem:
            logger.debug(f"[{nome_amostra}] Colônia filtrada por estar fora da margem r_margem (centro: {center_colonia}, raio placa: {r_margem})")
            continue

        # PONTO 1: Filtro para colônias excessivamente grandes em relação à placa.
        # Este filtro ajuda a remover, por exemplo, a própria placa se mal segmentada ou grandes artefatos.
        # Considerar tornar MAX_COLONY_RADIUS_FACTOR_OF_PETRI_MARGIN configurável.
        if radius_colonia_float > (r_margem * MAX_COLONY_RADIUS_FACTOR_OF_PETRI_MARGIN):
            logger.info(f"[{nome_amostra}] Colônia grande filtrada (raio colônia: {radius_colonia_float:.2f}px > {MAX_COLONY_RADIUS_FACTOR_OF_PETRI_MARGIN*100}% do raio da placa r_margem: {r_margem * MAX_COLONY_RADIUS_FACTOR_OF_PETRI_MARGIN:.2f}px)")
            total_filtradas_tamanho_maximo +=1
            continue

        mean_color_bgr = cv2.mean(img, mask=mask_colonia)[:3] # Média de cor na imagem original, dentro da máscara da colônia
        hsv_pixel = cv2.cvtColor(np.uint8([[mean_color_bgr]]), cv2.COLOR_BGR2HSV)
        tipo = classificar_cor_hsv(hsv_pixel[0][0])
        classificacoes_cores.append(tipo)
        
        cor_desenho = (0, 0, 255) # Bege (padrão)
        if tipo == 'amarela': cor_desenho = (0, 255, 255) # Amarelo
        elif tipo == 'rosada': cor_desenho = (203, 192, 255) # Rosa claro
        elif tipo == 'clara': cor_desenho = (255, 255, 255) # Branco
        cv2.circle(desenhar, center_colonia, radius_colonia_int, cor_desenho, 2)
        total_desenhadas += 1
    logger.info(f"[{nome_amostra}] Tempo para loop de marcadores e classificação: {time.time() - loop_marcadores_start_time:.4f}s")

    resumo_contagem = dict(Counter(classificacoes_cores))
    resumo_contagem['total'] = total_desenhadas # O total é o número de colônias efetivamente desenhadas/contadas
    
    logger.info(f"[{nome_amostra}] Resultados da contagem: Avaliadas={total_avaliadas}, "
                f"Filtradas Área={total_filtradas_area}, Filtradas Circ.={total_filtradas_circularidade}, "
                f"Filtradas Tam.Max={total_filtradas_tamanho_maximo}, Desenhadas/Total Final={total_desenhadas}. "
                f"Detalhe cores: {resumo_contagem}")
    logger.info(f"[{nome_amostra}] Tempo do núcleo de processamento (segmentação e filtros): {time.time() - core_processing_start_time:.4f}s")

    # --- Lógica de Densidade e Estimativa ---
    total_contado_na_subarea = resumo_contagem.get('total', 0)
    
    area_pixel_r_margem = np.pi * (r_margem ** 2)  # Área em pixels dentro de r_margem (subárea analisada)
    area_pixel_r_total_placa = np.pi * (r ** 2)     # Área em pixels da placa inteira detectada (raio r)

    densidade_na_subarea_cm2 = 0.0
    estimativa_extrapolada_placa_padrao = float(total_contado_na_subarea) # Padrão
    area_efetiva_r_margem_cm2 = 0.0

    # PONTO 2: Simplificação da condição. r > 0 já foi garantido. AREA_PADRAO_PLACA_CM2 é constante positiva.
    if area_pixel_r_total_placa > 0: # Garante que r > 0, o que já deve ser verdade aqui
        fracao_area_pixel_amostrada = area_pixel_r_margem / area_pixel_r_total_placa # Deve ser ~0.81 se r_margem = 0.9r
        # PONTO 4: Logar a fração da área amostrada
        logger.info(f"[{nome_amostra}] Fração da área da placa (pixels) amostrada (r_margem/r)^2: {fracao_area_pixel_amostrada:.4f}")
        
        area_efetiva_r_margem_cm2 = fracao_area_pixel_amostrada * AREA_PADRAO_PLACA_CM2
        
        if area_efetiva_r_margem_cm2 > 0.001: # Evitar divisão por área muito pequena
            densidade_na_subarea_cm2 = total_contado_na_subarea / area_efetiva_r_margem_cm2
            estimativa_extrapolada_placa_padrao = densidade_na_subarea_cm2 * AREA_PADRAO_PLACA_CM2
            logger.info(f"[{nome_amostra}] Cálculo de densidade (extrap.): "
                        f"Total Subárea ({area_efetiva_r_margem_cm2:.2f}cm²): {total_contado_na_subarea} UFC, "
                        f"Densidade Subárea: {densidade_na_subarea_cm2:.2f} UFC/cm², "
                        f"Estimativa Placa Padrão ({AREA_PADRAO_PLACA_CM2}cm²): {estimativa_extrapolada_placa_padrao:.2f} UFC")
        else:
            logger.warning(f"[{nome_amostra}] Área efetiva da subamostra (r_margem) em cm² é muito pequena ou zero ({area_efetiva_r_margem_cm2:.4f} cm²). "
                           f"Usando contagem direta ({total_contado_na_subarea}) como estimativa e densidade 0.")
            # Se a área efetiva é zero, a densidade não pode ser calculada de forma significativa.
            # A estimativa será apenas a contagem na subárea, e a densidade será 0.
            densidade_na_subarea_cm2 = 0.0 # Ou algum valor indicativo de erro/não calculado
            estimativa_extrapolada_placa_padrao = float(total_contado_na_subarea)

    else: # Este caso não deveria ocorrer se r > 0 é imposto no início.
        logger.warning(f"[{nome_amostra}] Área total da placa em pixels (baseada em r={r}) é zero. Usando contagem direta como estimativa.")
        estimativa_extrapolada_placa_padrao = float(total_contado_na_subarea)
        densidade_na_subarea_cm2 = 0.0 # Densidade não pode ser calculada

    # --- Fim da Lógica de Densidade e Estimativa ---

    hora_brasilia = datetime.now(timezone.utc) - timedelta(hours=3)
    texto_cabecalho = [
        f"{nome_amostra}",
        f"{hora_brasilia.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Total Contado (subárea {r_margem/r*100:.0f}%): {total_contado_na_subarea} UFC",
        f"Densidade (subárea): {densidade_na_subarea_cm2:.2f} UFC/cm^2",
        f"Estimativa Extrap. ({AREA_PADRAO_PLACA_CM2:.1f} cm^2): {round(estimativa_extrapolada_placa_padrao):.0f} UFC" # Arredonda para inteiro
    ]
    
    altura_legenda = 22 * len(texto_cabecalho) + 20
    # Ajustar largura da legenda para o conteúdo ou manter como estava
    largura_max_texto = 0
    for linha_texto in texto_cabecalho:
        (text_width, _), _ = cv2.getTextSize(linha_texto, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
        if text_width > largura_max_texto:
            largura_max_texto = text_width
    largura_legenda = min(max(380, largura_max_texto + 20), desenhar.shape[1] - 10)

    cv2.rectangle(desenhar, (5, 5), (largura_legenda, 5 + altura_legenda), (0, 0, 0), -1)

    for i, linha in enumerate(texto_cabecalho):
        y_texto = 25 + i * 22
        cv2.putText(desenhar, linha, (10, y_texto), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

    encode_start_time = time.time()
    _, buffer = cv2.imencode('.jpg', desenhar)
    logger.info(f"[{nome_amostra}] Tempo para encodificar imagem: {time.time() - encode_start_time:.4f}s")

    feedback_headers = {
        "X-Resumo-Total": str(total_contado_na_subarea),
        "X-Resumo-Amarela": str(resumo_contagem.get('amarela',0)),
        "X-Resumo-Bege": str(resumo_contagem.get('bege',0)),
        "X-Resumo-Clara": str(resumo_contagem.get('clara',0)),
        "X-Resumo-Rosada": str(resumo_contagem.get('rosada',0)),
        "X-Feedback-Avaliadas": str(total_avaliadas),
        "X-Feedback-Filtradas-Area": str(total_filtradas_area),
        "X-Feedback-Filtradas-Circularidade": str(total_filtradas_circularidade),
        "X-Feedback-Filtradas-Tamanho-Maximo": str(total_filtradas_tamanho_maximo), # Novo
        "X-Feedback-Desenhadas": str(total_desenhadas),
        "X-Feedback-Raio-Detectado-Px": str(r), # Raio total da placa detectada
        "X-Feedback-Area-Amostrada-Cm2": f"{area_efetiva_r_margem_cm2:.2f}",
        "X-Feedback-Densidade-Colonias-Cm2": f"{densidade_na_subarea_cm2:.2f}",
        "X-Feedback-Estimativa-Total-Colonias": f"{round(estimativa_extrapolada_placa_padrao):.0f}" # Arredondado
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
        resumo_da_contagem, imagem_processada, response_headers_dict = processar_imagem(
            conteudo_arquivo, nome_amostra, x_manual=x, y_manual=y, r_manual=r
        )
        
        return StreamingResponse(imagem_processada, media_type="image/jpeg", headers=response_headers_dict)

    except ValueError as e: # Erros como falha na decodificação da imagem
        logger.error(f"Erro de valor (ex: decodificação) para {nome_amostra}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException as e: # Erros HTTP explicitamente levantados (ex: placa não detectada)
        logger.warning(f"HTTPException para {nome_amostra}: {e.detail} (Status: {e.status_code})")
        # Re-levantar a exceção para que o FastAPI a trate corretamente
        raise e 
    except Exception as e: # Outros erros inesperados
        logger.exception(f"Erro interno inesperado durante o processamento para {nome_amostra}")
        raise HTTPException(status_code=500, detail="Erro interno no servidor. Tente novamente mais tarde.")
