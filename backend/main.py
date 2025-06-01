from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import numpy as np
import cv2
from io import BytesIO
from collections import Counter
from datetime import datetime
import pandas as pd
import os
import logging
from scipy import ndimage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="API de Contagem de Colônias",
    description="Processa imagens de placas de Petri para contar e classificar colônias.",
    version="1.5.0"
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
        "X-Feedback-Desenhadas", "X-Feedback-Raio"
    ]
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
        logger.info(f"Placa detectada com centro em ({circulos[0][0][0]}, {circulos[0][0][1]}) e raio {circulos[0][0][2]}")
        return circulos[0][0]
    logger.warning("Nenhuma placa detectada na imagem.")
    return None

def processar_imagem(imagem_bytes: bytes, nome_amostra: str, x_manual=None, y_manual=None, r_manual=None):
    file_bytes = np.asarray(bytearray(imagem_bytes), dtype=np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Não foi possível decodificar a imagem.")

    desenhar = img.copy()
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    if x_manual is not None and y_manual is not None and r_manual is not None:
        x, y, r = int(x_manual), int(y_manual), int(r_manual)
        logger.info(f"Usando parâmetros manuais para a placa: ({x}, {y}, {r})")
    else:
        circulo = detectar_placa(gray)
        if circulo is None:
            raise HTTPException(status_code=422, detail="Não foi possível detectar a placa de Petri automaticamente.")
        x, y, r = circulo

    r_margem = int(r * 0.90)
    mask_placa = np.zeros(gray.shape, dtype=np.uint8)
    cv2.circle(mask_placa, (x, y), r_margem, 255, -1)
    img_masked = cv2.bitwise_and(img, img, mask=mask_placa)
    gray_masked = cv2.bitwise_and(gray, gray, mask=mask_placa)
    gray_eq = cv2.equalizeHist(gray_masked)
    blurred = cv2.GaussianBlur(gray_eq, (5, 5), 0)

    thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY_INV, 41, 4)
    opened = cv2.morphologyEx(thresh, cv2.MORPH_OPEN,
                               cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    dist_transform = cv2.distanceTransform(opened, cv2.DIST_L2, 5)
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

        if area < 1.0 or area > 800:
            total_filtradas_area += 1
            continue

        perimeter = cv2.arcLength(cnt, True)
        if perimeter == 0:
            continue
        circularity = 4 * np.pi * (area / (perimeter * perimeter))
        if circularity < 0.35:
            total_filtradas_circularidade += 1
            continue

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

    # Adicionando metadados na imagem
    texto_cabecalho = [
    f"{nome_amostra}",
    f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (Brasília)",
    f"Total: {resumo_contagem['total']} UFC",
    f"Densidade: {densidade:.2f} UFC/cm²"
]

y0 = 25
for i, linha in enumerate(texto_cabecalho):
    y = y0 + i * 22
    cv2.putText(desenhar, linha, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)

    _, buffer = cv2.imencode('.jpg', desenhar)
    feedback_headers = {
        "X-Feedback-Avaliadas": str(total_avaliadas),
        "X-Feedback-Filtradas-Area": str(total_filtradas_area),
        "X-Feedback-Filtradas-Circularidade": str(total_filtradas_circularidade),
        "X-Feedback-Desenhadas": str(total_desenhadas),
        "X-Feedback-Raio": str(r)
    }

    return resumo_contagem, BytesIO(buffer.tobytes()), feedback_headers

@app.post("/contar/", summary="Conta e classifica colônias em uma imagem")
async def contar_colonias_endpoint(
    file: UploadFile = File(..., description="Imagem da placa de Petri"),
    nome_amostra: str = Form(..., description="Identificação da amostra."),
    x: int = Form(None),
    y: int = Form(None),
    r: int = Form(None)
):
    conteudo_arquivo = await file.read()
    if not conteudo_arquivo:
        raise HTTPException(status_code=400, detail="Arquivo enviado está vazio.")
    
    resumo, imagem_processada, feedback = processar_imagem(conteudo_arquivo, nome_amostra, x_manual=x, y_manual=y, r_manual=r)
    headers = {f"X-Resumo-{k.capitalize()}": str(v) for k, v in resumo.items()}
    headers.update(feedback)

    # 📋 LOG DA ANÁLISE
    now = datetime.now()
    data_hora = now.strftime("%Y-%m-%d %H:%M:%S")
    raio = int(feedback.get("X-Feedback-Raio", r or 0))
    area_amostrada = round(3.1416 * ((raio * 0.90) ** 2) / 100, 2)
    densidade = round(resumo.get('total', 0) / area_amostrada, 2) if area_amostrada > 0 else 0
    estimativa_total = round(densidade * 57.5, 2)

    dados_log = {
        "amostra": nome_amostra,
        "data_hora": data_hora,
        "total": resumo.get('total', 0),
        "amarela": resumo.get('amarela', 0),
        "bege": resumo.get('bege', 0),
        "clara": resumo.get('clara', 0),
        "rosada": resumo.get('rosada', 0),
        "avaliadas": feedback.get("X-Feedback-Avaliadas", 0),
        "filtradas_area": feedback.get("X-Feedback-Filtradas-Area", 0),
        "filtradas_circ": feedback.get("X-Feedback-Filtradas-Circularidade", 0),
        "desenhadas": feedback.get("X-Feedback-Desenhadas", 0),
        "area_amostrada_cm2": area_amostrada,
        "densidade_colonias_cm2": densidade,
        "estimativa_total_colonias": estimativa_total
    }

    caminho_log = "logs_colonias.csv"
    df_log = pd.DataFrame([dados_log])
    if os.path.exists(caminho_log):
        df_log.to_csv(caminho_log, mode='a', header=False, index=False)
    else:
        df_log.to_csv(caminho_log, index=False)

    return StreamingResponse(imagem_processada, media_type="image/jpeg", headers=headers)
