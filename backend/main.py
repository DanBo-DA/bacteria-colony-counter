from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import numpy as np
import cv2
from io import BytesIO

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    for c in contours:
        area = cv2.contourArea(c)
        if 20 < area < 3000:
            colonias.append(c)

    for c in colonias:
        (x, y), radius = cv2.minEnclosingCircle(c)
        center = (int(x), int(y))
        radius = int(radius)
        cv2.circle(original, center, radius, (0, 0, 255), 2)

    _, buffer = cv2.imencode('.jpg', original)
    img_bytes = BytesIO(buffer.tobytes())

    return len(colonias), img_bytes

@app.post("/contar")
async def contar_colonias(file: UploadFile = File(...)):
    conteudo = await file.read()
    total, imagem_processada = processar_imagem(conteudo)
    return StreamingResponse(imagem_processada, media_type="image/jpeg", headers={"X-Colonias": str(total)})
