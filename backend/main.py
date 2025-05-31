from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import numpy as np
import cv2
from io import BytesIO
from collections import Counter
import logging # Adicionado para logging
import math # Adicionado para math.pi (circularidade)

# Configuração básica de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="API de Contagem de Colônias",
    description="Processa imagens de placas de Petri para contar e classificar colônias.",
    version="1.2.0" # Versão incrementada
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, restrinja para as origens permitidas
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def classificar_cor_hsv(hsv_color_mean):
    """
    Classifica a cor média de uma colônia com base nos seus componentes HSV.
    Os ranges de H (Matiz), S (Saturação) e V (Valor/Brilho) precisam ser calibrados
    cuidadosamente com base nas suas amostras de colônias e condições de iluminação.

    H: 0-179 (em OpenCV)
    S: 0-255
    V: 0-255
    """
    h, s, v = hsv_color_mean

    # Exemplo de ranges (PRECISAM DE CALIBRAÇÃO):
    # Colônias Claras/Brancas: Baixa saturação, alto valor
    if s < 40 and v > 190: # Saturação muito baixa, muito claro
        return 'clara'
    # Colônias Amarelas: Matiz na faixa do amarelo, saturação e valor médios/altos
    elif 20 <= h <= 35 and s > 60 and v > 60: # Matiz amarelo/laranja claro
        return 'amarela'
    # Colônias Rosadas: Matiz na faixa do rosa/vermelho, saturação e valor médios/altos
    elif (0 <= h <= 15 or 160 <= h <= 179) and s > 60 and v > 60: # Matiz vermelho/magenta
        return 'rosada'
    # Outras cores ou colônias mais escuras/menos saturadas podem cair aqui
    else:
        return 'bege' # Categoria padrão

def processar_imagem(imagem_bytes: bytes):
    """
    Processa a imagem para detectar, contar e classificar colônias.
    """
    try:
        file_bytes = np.asarray(bytearray(imagem_bytes), dtype=np.uint8)
        img_original_colorida = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

        if img_original_colorida is None:
            logger.error("Falha ao decodificar a imagem. Verifique o formato do arquivo.")
            raise ValueError("Não foi possível decodificar a imagem. O arquivo pode estar corrompido ou em um formato não suportado.")
        
        original_para_desenho = img_original_colorida.copy()

        # Converter para escala de cinza
        gray = cv2.cvtColor(img_original_colorida, cv2.COLOR_BGR2GRAY)

        # Usar equalização de histograma global
        gray_equalizada = cv2.equalizeHist(gray)
        # Alternativa: CLAHE para contraste local (pode ser melhor para iluminação irregular)
        # clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        # gray_equalizada = clahe.apply(gray)


        # Desfoque Gaussiano para suavizar a imagem e reduzir ruído
        blurred = cv2.GaussianBlur(gray_equalizada, (5, 5), 0)

        # Limiarização adaptativa para binarizar a imagem
        # Parâmetros (blockSize, C) são cruciais e precisam de ajuste:
        # blockSize: Tamanho da vizinhança (ímpar, ex: 11, 15, 17, 21 ...)
        # C: Constante subtraída da média (ex: 2, 3, 5, 7 ...)
        thresh = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 15, 5 # AJUSTE AQUI: blockSize=15, C=5 (experimentar)
        )

        # Operações morfológicas para limpar a imagem binarizada
        # Abertura (OPEN): Remove pequenos ruídos brancos (colônias falsas)
        kernel_abertura = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        morphed_aberta = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel_abertura)

        # Fechamento (CLOSE): Preenche pequenos buracos pretos dentro das colônias
        kernel_fechamento = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)) # AJUSTE AQUI: kernel (5,5)
        morphed_final = cv2.morphologyEx(morphed_aberta, cv2.MORPH_CLOSE, kernel_fechamento)

        # Encontrar contornos das possíveis colônias
        contours, _ = cv2.findContours(morphed_final, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        colonias_detectadas = []
        classificacoes_cores = []

        for contorno in contours:
            area = cv2.contourArea(contorno)
            
            # Filtrar contornos por área
            # Estes limites (AJUSTE AQUI: 30 e 2800) são exemplos e DEVEM ser ajustados
            if 30 < area < 2800:
                perimetro = cv2.arcLength(contorno, True)
                if perimetro == 0: continue # Evitar divisão por zero

                # Filtro de Circularidade: (4 * pi * Area) / (Perimetro^2)
                # Valores mais próximos de 1 são mais circulares.
                circularidade = (4 * math.pi * area) / (perimetro * perimetro)
                
                # AJUSTE AQUI: Limiar de circularidade (ex: 0.65)
                if circularidade > 0.60:
                    mask = np.zeros(gray.shape, np.uint8)
                    cv2.drawContours(mask, [contorno], -1, 255, -1)

                    mean_color_bgr = cv2.mean(img_original_colorida, mask=mask)[:3]
                    mean_color_bgr_pixel = np.uint8([[mean_color_bgr]])
                    hsv_pixel = cv2.cvtColor(mean_color_bgr_pixel, cv2.COLOR_BGR2HSV)
                    mean_hsv = hsv_pixel[0][0]

                    tipo_cor = classificar_cor_hsv(mean_hsv)
                    classificacoes_cores.append(tipo_cor)
                    colonias_detectadas.append({'contorno': contorno, 'tipo': tipo_cor, 'cor_media_bgr': mean_color_bgr, 'area': area, 'circularidade': circularidade})
        
        logger.info(f"Contornos brutos encontrados: {len(contours)}")
        logger.info(f"Colônias após filtros (área e circularidade): {len(colonias_detectadas)}")

        # Desenhar círculos e informações na imagem original
        for colonia in colonias_detectadas:
            cnt = colonia['contorno']
            tipo = colonia['tipo']

            (x, y), radius = cv2.minEnclosingCircle(cnt)
            center = (int(x), int(y))
            radius = int(radius)

            cor_desenho = (0, 0, 255) 
            if tipo == 'amarela':
                cor_desenho = (0, 255, 255)
            elif tipo == 'rosada':
                cor_desenho = (203, 192, 255) 
            elif tipo == 'clara':
                cor_desenho = (255, 255, 255)
            
            cv2.circle(original_para_desenho, center, radius, cor_desenho, 2)
            # Opcional: Adicionar texto com o tipo ou área/circularidade para depuração
            # texto_debug = f"{tipo} A:{int(colonia['area'])} C:{colonia['circularidade']:.2f}"
            # cv2.putText(original_para_desenho, texto_debug, (center[0], center[1] - radius - 5),
            #             cv2.FONT_HERSHEY_SIMPLEX, 0.3, cor_desenho, 1)

        success, buffer = cv2.imencode('.jpg', original_para_desenho)
        if not success:
            logger.error("Falha ao codificar a imagem processada para JPEG.")
            raise ValueError("Não foi possível codificar a imagem processada.")
        
        img_bytes_io = BytesIO(buffer.tobytes())

        resumo_contagem = dict(Counter(classificacoes_cores))
        resumo_contagem['total'] = len(classificacoes_cores)
        
        logger.info(f"Resumo da contagem: {resumo_contagem}")

        return resumo_contagem, img_bytes_io

    except ValueError as ve:
        logger.error(f"Erro de valor durante o processamento: {ve}")
        raise
    except cv2.error as cv_err:
        logger.error(f"Erro OpenCV: {cv_err}")
        raise HTTPException(status_code=500, detail=f"Erro interno no processamento de imagem (OpenCV): {str(cv_err)}")
    except Exception as e:
        logger.exception("Erro inesperado durante o processamento da imagem.")
        raise HTTPException(status_code=500, detail=f"Ocorreu um erro inesperado no servidor: {str(e)}")


@app.post("/contar/",
          summary="Conta e classifica colônias em uma imagem",
          response_description="Imagem processada com colônias destacadas e contagem nos cabeçalhos X-Resumo-...")
async def contar_colonias_endpoint(file: UploadFile = File(..., description="Arquivo de imagem da placa de Petri.")):
    """
    Recebe uma imagem de uma placa de Petri, processa-a para identificar,
    contar e classificar colônias por cor.

    Retorna a imagem processada com as detecções e um resumo da contagem
    nos cabeçalhos da resposta (ex: `X-Resumo-Total`, `X-Resumo-Amarela`).
    """
    try:
        conteudo_arquivo = await file.read()
        if not conteudo_arquivo:
            logger.warning("Tentativa de upload de arquivo vazio.")
            raise HTTPException(status_code=400, detail="Arquivo enviado está vazio.")

        resumo, imagem_processada_bytes_io = processar_imagem(conteudo_arquivo)

        headers = {}
        for k, v in resumo.items():
            header_key = f"X-Resumo-{k.replace('_', '-').capitalize()}"
            headers[header_key] = str(v)
        
        logger.info(f"Enviando resposta com cabeçalhos: {headers}")

        return StreamingResponse(imagem_processada_bytes_io, media_type="image/jpeg", headers=headers)

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.exception(f"Erro não tratado no endpoint /contar/: {e}")
        raise HTTPException(status_code=500, detail="Erro interno no servidor ao processar a requisição.")

# Para executar localmente com Uvicorn (exemplo):
# import uvicorn
# if __name__ == "__main__":
#     uvicorn.run(app, host="0.0.0.0", port=8000)

