from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import numpy as np
import cv2
from io import BytesIO
from collections import Counter
import logging # Adicionado para logging

# Configuração básica de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="API de Contagem de Colônias",
    description="Processa imagens de placas de Petri para contar e classificar colônias.",
    version="1.1.0"
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

        # Aplicar CLAHE para melhorar o contraste localmente
        # clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        # gray_clahe = clahe.apply(gray)
        # Usar equalização de histograma global se CLAHE não for preferível
        gray_equalizada = cv2.equalizeHist(gray)


        # Desfoque Gaussiano para suavizar a imagem e reduzir ruído
        # Um kernel maior pode ser necessário para imagens com mais ruído ou colônias maiores
        blurred = cv2.GaussianBlur(gray_equalizada, (5, 5), 0) # Kernel (5,5) ou (7,7) podem ser testados

        # Limiarização adaptativa para binarizar a imagem
        # Parâmetros (blockSize, C) são cruciais e precisam de ajuste:
        # blockSize: Tamanho da vizinhança (ímpar, ex: 11, 15, 21, 31 ...)
        # C: Constante subtraída da média (ex: 2, 3, 5 ...)
        thresh = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 21, 3 # Valores de exemplo, ajuste conforme necessário
        )

        # Operações morfológicas para limpar a imagem binarizada
        # Abertura (OPEN): Remove pequenos ruídos brancos (colônias falsas)
        # Kernel maior remove objetos maiores.
        kernel_abertura = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)) # (3,3) ou (5,5)
        morphed = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel_abertura)

        # Fechamento (CLOSE): Preenche pequenos buracos pretos dentro das colônias
        # Descomente se necessário e ajuste o kernel.
        # kernel_fechamento = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        # morphed = cv2.morphologyEx(morphed, cv2.MORPH_CLOSE, kernel_fechamento)

        # Encontrar contornos das possíveis colônias
        contours, _ = cv2.findContours(morphed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        colonias_detectadas = []
        classificacoes_cores = []

        for contorno in contours:
            area = cv2.contourArea(contorno)
            # Filtrar contornos por área para remover ruídos ou objetos muito grandes
            # Estes limites (50 e 2500) são exemplos e DEVEM ser ajustados
            if 50 < area < 3500: # Aumentei um pouco o limite inferior e superior
                # Criar uma máscara para a colônia atual
                mask = np.zeros(gray.shape, np.uint8)
                cv2.drawContours(mask, [contorno], -1, 255, -1) # Preenche o contorno

                # Calcular a cor média da colônia na imagem colorida original
                mean_color_bgr = cv2.mean(img_original_colorida, mask=mask)[:3] # (B, G, R)

                # Converter a cor média BGR para HSV para classificação
                # cv2.cvtColor espera um array 3D (1x1 pixel com 3 canais)
                mean_color_bgr_pixel = np.uint8([[mean_color_bgr]])
                hsv_pixel = cv2.cvtColor(mean_color_bgr_pixel, cv2.COLOR_BGR2HSV)
                mean_hsv = hsv_pixel[0][0] # (H, S, V)

                tipo_cor = classificar_cor_hsv(mean_hsv)
                classificacoes_cores.append(tipo_cor)
                colonias_detectadas.append({'contorno': contorno, 'tipo': tipo_cor, 'cor_media_bgr': mean_color_bgr})
        
        logger.info(f"Contornos brutos encontrados: {len(contours)}")
        logger.info(f"Colônias filtradas por área: {len(colonias_detectadas)}")

        # Desenhar círculos e informações na imagem original
        for colonia in colonias_detectadas:
            cnt = colonia['contorno']
            tipo = colonia['tipo']

            (x, y), radius = cv2.minEnclosingCircle(cnt)
            center = (int(x), int(y))
            radius = int(radius)

            # Definir cor do círculo com base na classificação
            cor_desenho = (0, 0, 255) # Vermelho padrão (para 'bege' ou não classificado)
            if tipo == 'amarela':
                cor_desenho = (0, 255, 255)  # Amarelo (BGR)
            elif tipo == 'rosada':
                cor_desenho = (203, 192, 255) # Rosa claro (BGR) - (era magenta, pode ser muito forte)
            elif tipo == 'clara':
                cor_desenho = (255, 255, 255)  # Branco (BGR)
            
            cv2.circle(original_para_desenho, center, radius, cor_desenho, 2)
            # Opcional: Adicionar texto com o tipo perto da colônia
            # cv2.putText(original_para_desenho, tipo, (center[0], center[1] - radius - 5),
            #             cv2.FONT_HERSHEY_SIMPLEX, 0.4, cor_desenho, 1)

        # Codificar a imagem processada para envio
        success, buffer = cv2.imencode('.jpg', original_para_desenho)
        if not success:
            logger.error("Falha ao codificar a imagem processada para JPEG.")
            raise ValueError("Não foi possível codificar a imagem processada.")
        
        img_bytes_io = BytesIO(buffer.tobytes())

        # Preparar resumo da contagem
        resumo_contagem = dict(Counter(classificacoes_cores))
        resumo_contagem['total'] = len(classificacoes_cores)
        
        logger.info(f"Resumo da contagem: {resumo_contagem}")

        return resumo_contagem, img_bytes_io

    except ValueError as ve: # Erros esperados de validação ou processamento
        logger.error(f"Erro de valor durante o processamento: {ve}")
        raise # Re-levanta a exceção para ser tratada pelo endpoint FastAPI
    except cv2.error as cv_err:
        logger.error(f"Erro OpenCV: {cv_err}")
        raise HTTPException(status_code=500, detail=f"Erro interno no processamento de imagem (OpenCV): {str(cv_err)}")
    except Exception as e:
        logger.exception("Erro inesperado durante o processamento da imagem.") # Loga o traceback completo
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
            # Sanitiza a chave para ser um nome de cabeçalho HTTP válido e mais legível
            header_key = f"X-Resumo-{k.replace('_', '-').capitalize()}"
            headers[header_key] = str(v)
        
        logger.info(f"Enviando resposta com cabeçalhos: {headers}")

        return StreamingResponse(imagem_processada_bytes_io, media_type="image/jpeg", headers=headers)

    except ValueError as ve: # Captura erros de processar_imagem que são ValueError
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException as http_exc: # Re-levanta HTTPExceptions já tratadas
        raise http_exc
    except Exception as e:
        logger.exception(f"Erro não tratado no endpoint /contar/: {e}")
        raise HTTPException(status_code=500, detail="Erro interno no servidor ao processar a requisição.")

# Para executar localmente com Uvicorn (exemplo):
# import uvicorn
# if __name__ == "__main__":
#     uvicorn.run(app, host="0.0.0.0", port=8000)

