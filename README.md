# 🧫 Colony Counter API - README

## 📄 Description
This FastAPI-based application processes images of Petri dishes to count and classify bacterial colonies based on their shape and color. It uses image processing and segmentation techniques to detect colonies, and classifies them into four color categories: `amarela`, `bege`, `clara`, and `rosada`.

## 🚀 Features
- Automatic detection of Petri dish using Hough Circle Transform
- Manual override for dish coordinates and radius (x, y, r)
- Classification of colonies based on color in HSV space
- Filtering by area and circularity to improve accuracy
- Visualization output with colored circles indicating colony classification
- Response headers include a detailed summary and filtering feedback

## 📬 API Endpoint
### `POST /contar/`
**Description:** Count and classify colonies in a Petri dish image.

**Parameters:**
- `file` (form-data, required): Image of the Petri dish (`.jpg`, `.png`)
- `x` (form-data, optional): X-coordinate of the plate center. Auto-detected if not provided
- `y` (form-data, optional): Y-coordinate of the plate center. Auto-detected if not provided
- `r` (form-data, optional): Radius of the plate. Auto-detected if not provided

**Response:**
- A JPEG image with annotated colony detections
- Response headers with detection summary and feedback:
  - `X-Resumo-Total`, `X-Resumo-Amarela`, etc.
  - `X-Feedback-Avaliadas`, `X-Feedback-Filtradas-Area`, `X-Feedback-Filtradas-Circularidade`, `X-Feedback-Desenhadas`

**Error Handling:**
- Returns 422 if no Petri dish is detected and no manual coordinates are provided

## 📦 Requirements
```bash
pip install fastapi uvicorn opencv-python numpy python-multipart scipy
```

## 🛠️ Run Locally
```bash
uvicorn main:app --reload
```
Then open: `http://127.0.0.1:8000/docs` to interact with the API using Swagger UI.

## 📌 Update Notes
### Version 1.4.0
- ➕ Added manual override for plate detection via `x`, `y`, `r` parameters
- 🛠 Improved error message when automatic detection fails
- 📤 Included detection feedback in response headers
- 🔍 Refined filtering by area and circularity for better accuracy
- 🧪 Added more robust classification via HSV mean filtering

## 🔮 Future Work
- [ ]  Allow user to draw ROI (Region of Interest) manually on `/docs` interface
- [ ]  Improve support for noisy backgrounds and complex lighting
- [ ]  Train a ML model to further improve classification

---
## 📄 License
MIT License © 2025 Lucas Daniel Borges Lopes
