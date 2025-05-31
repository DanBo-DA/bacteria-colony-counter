from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import numpy as np
import cv2
from io import BytesIO
from collections import Counter
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="API de Contagem de Colônias",
    description="Processa imagens de placas de Petri para contar e classificar colônias.",
    version="1.3.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    img_blur = cv2.medianBlur(img_gray, 5)
    circulos = cv2.HoughCircles(img_blur, cv2.HOUGH_GRADIENT, dp=1.2, minDist=100,
                                 param1=50, param2=30, minRadius=100, maxRadius=0)
    if circulos is not None:
        circulos = np.uint16(np.around(circulos))
        return circulos[0][0]  # x, y, r
    return None

def processar_imagem(imagem_bytes: bytes):
    try:
        file_bytes = np.asarray(bytearray(imagem_bytes), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

        if img is None:
            raise ValueError("Não foi possível decodificar a imagem.")

        desenhar = img.copy()
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        circulo = detectar_placa(gray)
        if circulo is None:
            raise ValueError("Não foi possível detectar a placa de Petri na imagem.")

        x, y, r = circulo
        mask_placa = np.zeros(gray.shape, dtype=np.uint8)
        cv2.circle(mask_placa, (x, y), r, 255, -1)

        img_masked = cv2.bitwise_and(img, img, mask=mask_placa)
        gray_masked = cv2.bitwise_and(gray, gray, mask=mask_placa)
        gray_eq = cv2.equalizeHist(gray_masked)
        blurred = cv2.GaussianBlur(gray_eq, (5, 5), 0)
        thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                       cv2.THRESH_BINARY_INV, 21, 3)
        opened = cv2.morphologyEx(thresh, cv2.MORPH_OPEN,
                                   cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))

        dist_transform = cv2.distanceTransform(opened, cv2.DIST_L2, 5)
        _, sure_fg = cv2.threshold(dist_transform, 0.4 * dist_transform.max(), 255, 0)
        sure_fg = np.uint8(sure_fg)
        unknown = cv2.subtract(opened, sure_fg)

        _, markers = cv2.connectedComponents(sure_fg)
        markers = markers + 1
        markers[unknown == 255] = 0
        markers = cv2.watershed(img_masked, markers)

        classificacoes_cores = []
        for marker in np.unique(markers):
            if marker <= 1:
                continue
            mask = np.uint8(markers == marker) * 255
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                continue
            cnt = contours[0]
            area = cv2.contourArea(cnt)
            if area < 2 or area > 800:
                continue
            perimeter = cv2.arcLength(cnt, True)
            if perimeter == 0:
                continue
            circularity = 4 * np.pi * (area / (perimeter * perimeter))
            if circularity < 0.65:
                continue

            mean_color_bgr = cv2.mean(img, mask=mask)[:3]
            hsv_pixel = cv2.cvtColor(np.uint8([[mean_color_bgr]]), cv2.COLOR_BGR2HSV)
            tipo = classificar_cor_hsv(hsv_pixel[0][0])
            classificacoes_cores.append(tipo)

            (cx, cy), radius = cv2.minEnclosingCircle(cnt)
            center = (int(cx), int(cy))
            radius = int(radius)
            if radius > 30:
                continue
            cor = (0, 0, 255)
            if tipo == 'amarela':
                cor = (0, 255, 255)
            elif tipo == 'rosada':
                cor = (203, 192, 255)
            elif tipo == 'clara':
                cor = (255, 255, 255)
            cv2.circle(desenhar, center, radius, cor, 2)

        resumo_contagem = dict(Counter(classificacoes_cores))
        resumo_contagem['total'] = len(classificacoes_cores)

        _, buffer = cv2.imencode('.jpg', desenhar)
        return resumo_contagem, BytesIO(buffer.tobytes())

    except Exception as e:
        logger.exception("Erro inesperado durante o processamento da imagem.")
        raise HTTPException(status_code=500, detail=f"Erro no processamento da imagem: {str(e)}")

@app.post("/contar/", summary="Conta e classifica colônias em uma imagem", response_description="Imagem com colônias marcadas e contagem nos headers")
async def contar_colonias_endpoint(file: UploadFile = File(...)):
    conteudo_arquivo = await file.read()
    if not conteudo_arquivo:
        raise HTTPException(status_code=400, detail="Arquivo enviado está vazio.")
    resumo, imagem_processada = processar_imagem(conteudo_arquivo)
    headers = {f"X-Resumo-{k.capitalize()}": str(v) for k, v in resumo.items()}
    return StreamingResponse(imagem_processada, media_type="image/jpeg", headers=headers)
