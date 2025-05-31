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
    blurred = cv2.GaussianBlur(gray, (11, 11), 0)
    _, thresh = cv2.threshold(blurred, 127, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    colonias = [c for c in contours if cv2.contourArea(c) > 50]

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
