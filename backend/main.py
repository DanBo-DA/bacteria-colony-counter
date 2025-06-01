# Importação de bibliotecas necessárias
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import numpy as np
import cv2
from io import BytesIO
from collections import Counter
import logging
from scipy import ndimage

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inicialização da aplicação FastAPI
app = FastAPI(
    title="API de Contagem de Colônias",
    description="Processa imagens de placas de Petri para contar e classificar colônias.",
    version="1.4.0"
)

# Middleware para permitir CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-Resumo-Total", "X-Resumo-Amarela", "X-Resumo-Bege", "X-Resumo-Clara", "X-Resumo-Rosada",
        "X-Feedback-Avaliadas", "X-Feedback-Filtradas-Area", "X-Feedback-Filtradas-Circularidade", "X-Feedback-Desenhadas"
    ]
)

# Função para classificar colônias por cor média em HSV
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

# Função para detectar automaticamente a placa de Petri com HoughCircles
def detectar_placa(img_gray):
    img_blur = cv2.medianBlur(img_gray, 5)
    circulos = cv2.HoughCircles(img_blur, cv2.HOUGH_GRADIENT, dp=1.2, minDist=100,
                                 param1=50, param2=30, minRadius=100, maxRadius=0)
    if circulos is not None:
        circulos = np.uint16(np.around(circulos))
        logger.info(f"Placa detectada com centro em ({circulos[0][0][0]}, {circulos[0][0][1]}) e raio {circulos[0][0][2]}")
        return circulos[0][0]  # x, y, r
    logger.warning("Nenhuma placa detectada na imagem.")
    return None

# Função principal para processamento da imagem
def processar_imagem(imagem_bytes: bytes, x_manual=None, y_manual=None, r_manual=None):
    try:
        file_bytes = np.asarray(bytearray(imagem_bytes), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Não foi possível decodificar a imagem.")

        logger.info(f"Imagem recebida com dimensões: {img.shape}")
        desenhar = img.copy()
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        if x_manual is not None and y_manual is not None and r_manual is not None:
            x, y, r = int(x_manual), int(y_manual), int(r_manual)
            logger.info(f"Usando parâmetros manuais para a placa: ({x}, {y}, {r})")
        else:
            circulo = detectar_placa(gray)
            if circulo is None:
                raise HTTPException(status_code=422, detail="Não foi possível detectar a placa de Petri automaticamente. Por favor, forneça os valores de x, y e r.")
            x, y, r = circulo

        r_margem = int(r * 0.90)
        mask_placa = np.zeros(gray.shape, dtype=np.uint8)
        cv2.circle(mask_placa, (x, y), r_margem, 255, -1)
        img_masked = cv2.bitwise_and(img, img, mask=mask_placa)
        gray_masked = cv2.bitwise_and(gray, gray, mask=mask_placa)
        gray_eq = cv2.equalizeHist(gray_masked)
        blurred = cv2.GaussianBlur(gray_eq, (5, 5), 0)

        # Parâmetros de binarização e abertura (já ajustados):
        thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                       cv2.THRESH_BINARY_INV, 41, 4)
        opened = cv2.morphologyEx(thresh, cv2.MORPH_OPEN,
                                   cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))

        dist_transform = cv2.distanceTransform(opened, cv2.DIST_L2, 5)

        # Parâmetro do ndimage.maximum_filter (já ajustado):
        local_max = ndimage.maximum_filter(dist_transform, size=10) == dist_transform

        markers, _ = ndimage.label(local_max)
        markers = markers + 1
        unknown = cv2.subtract(opened, np.uint8(local_max))
        markers[unknown == 255] = 0
        markers = cv2.watershed(img_masked, markers.astype(np.int32))

        classificacoes_cores = []
        total_avaliadas = 0
        total_filtradas_area = 0
        total_filtradas_circularidade = 0
        total_desenhadas = 0

        for marker in np.unique(markers):
            if marker <= 1:
                continue
            mask = np.uint8(markers == marker) * 255
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                continue
            cnt = contours[0]
            area = cv2.contourArea(cnt)
            total_avaliadas += 1

            # >>> INÍCIO DAS NOVAS MODIFICAÇÕES - FILTROS <<<

            # Ajuste do filtro de área: permitindo colônias um pouco menores (de 1.5 para 1.0)
            if area < 1.0 or area > 800: # Alterado aqui
                total_filtradas_area += 1
                continue
            
            perimeter = cv2.arcLength(cnt, True)
            if perimeter == 0:
                continue
            circularity = 4 * np.pi * (area / (perimeter * perimeter))

            # Ajuste do filtro de circularidade: permitindo formas menos circulares (de 0.45 para 0.35)
            if circularity < 0.35: # Alterado aqui
                total_filtradas_circularidade += 1
                continue

            # >>> FIM DAS NOVAS MODIFICAÇÕES - FILTROS <<<

            (cx, cy), radius = cv2.minEnclosingCircle(cnt)
            center = (int(cx), int(cy))
            radius = int(radius)
            if np.linalg.norm(np.array(center) - np.array((x, y))) > r_margem:
                continue

            mean_color_bgr = cv2.mean(img, mask=mask)[:3]
            hsv_pixel = cv2.cvtColor(np.uint8([[mean_color_bgr]]), cv2.COLOR_BGR2HSV)
            tipo = classificar_cor_hsv(hsv_pixel[0][0])
            classificacoes_cores.append(tipo)

            if radius > 50:
                continue
            cor = (0, 0, 255)
            if tipo == 'amarela':
                cor = (0, 255, 255)
            elif tipo == 'rosada':
                cor = (203, 192, 255)
            elif tipo == 'clara':
                cor = (255, 255, 255)
            cv2.circle(desenhar, center, radius, cor, 2)
            total_desenhadas += 1

        resumo_contagem = dict(Counter(classificacoes_cores))
        resumo_contagem['total'] = len(classificacoes_cores)

        logger.info(f"Total avaliadas: {total_avaliadas}, Filtradas por área: {total_filtradas_area}, "
                    f"Filtradas por circularidade: {total_filtradas_circularidade}, Desenhadas: {total_desenhadas}, "
                    f"Contagem final: {resumo_contagem}")

        _, buffer = cv2.imencode('.jpg', desenhar)
        feedback_headers = {
            "X-Feedback-Avaliadas": str(total_avaliadas),
            "X-Feedback-Filtradas-Area": str(total_filtradas_area),
            "X-Feedback-Filtradas-Circularidade": str(total_filtradas_circularidade),
            "X-Feedback-Desenhadas": str(total_desenhadas)
        }

        return resumo_contagem, BytesIO(buffer.tobytes()), feedback_headers

    except Exception as e:
        logger.exception("Erro inesperado durante o processamento da imagem.")
        raise HTTPException(status_code=500, detail=f"Erro no processamento da imagem: {str(e)}")

# Endpoint principal da API
@app.post(
    "/contar/",
    summary="Conta e classifica colônias em uma imagem",
    response_description="Imagem com colônias marcadas e contagem nos headers"
)
async def contar_colonias_endpoint(
    file: UploadFile = File(..., description="Imagem da placa de Petri. Pode ser .jpg ou .png."),
    x: int = Form(None, description="Coordenada X do centro da placa. Se não informado, será detectado automaticamente."),
    y: int = Form(None, description="Coordenada Y do centro da placa. Se não informado, será detectado automaticamente."),
    r: int = Form(None, description="Raio da placa em pixels. Se não informado, será detectado automaticamente.")
):
    conteudo_arquivo = await file.read()
    if not conteudo_arquivo:
        raise HTTPException(status_code=400, detail="Arquivo enviado está vazio.")
    resumo, imagem_processada, feedback = processar_imagem(conteudo_arquivo, x_manual=x, y_manual=y, r_manual=r)
    headers = {f"X-Resumo-{k.capitalize()}": str(v) for k, v in resumo.items()}
    headers.update(feedback)
    return StreamingResponse(imagem_processada, media_type="image/jpeg", headers=headers)
