from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import numpy as np
import cv2
from io import BytesIO
from collections import Counter

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def classificar_cor(mean_color):
    b, g, r = mean_color
    if r > 150 and g < 100:
        return 'rosada'
    elif g > 150 and r < 150:
        return 'amarela'
    elif sum(mean_color)/3 > 180:
        return 'clara'
    else:
        return 'bege'

def processar_imagem(imagem_bytes):
    file_bytes = np.asarray(bytearray(imagem_bytes), dtype=np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    original = img.copy()

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)

    thresh = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 11, 2
    )

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
    morphed = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(morphed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    colonias = []
    classificacoes = []
    for c in contours:
        area = cv2.contourArea(c)
        if 20 < area < 3000:
            mask = np.zeros(gray.shape, np.uint8)
            cv2.drawContours(mask, [c], -1, 255, -1)
            mean_color = cv2.mean(img, mask=mask)[:3]
            tipo = classificar_cor(mean_color)
            classificacoes.append(tipo)
            colonias.append((c, tipo))

    for c, tipo in colonias:
        (x, y), radius = cv2.minEnclosingCircle(c)
        center = (int(x), int(y))
        radius = int(radius)
        cor = (0, 0, 255)
        if tipo == 'amarela':
            cor = (0, 255, 255)
        elif tipo == 'rosada':
            cor = (255, 0, 255)
        elif tipo == 'clara':
            cor = (255, 255, 255)
        cv2.circle(original, center, radius, cor, 2)

    _, buffer = cv2.imencode('.jpg', original)
    img_bytes = BytesIO(buffer.tobytes())

    resumo = dict(Counter(classificacoes))
    resumo['total'] = len(classificacoes)

    return resumo, img_bytes

@app.post("/contar")
async def contar_colonias(file: UploadFile = File(...)):
    conteudo = await file.read()
    resumo, imagem_processada = processar_imagem(conteudo)
    headers = {"X-Colonias": str(resumo['total'])}
    for k, v in resumo.items():
        if k != 'total':
            headers[f"X-{k}"] = str(v)
    return StreamingResponse(imagem_processada, media_type="image/jpeg", headers=headers)
