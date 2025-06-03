# 🧫 Colony Counter API - README

## 📄 Description

This FastAPI-based application processes images of Petri dishes to count and classify bacterial colonies based on their shape and color. It uses image processing and segmentation techniques to detect colonies, and classifies them into four color categories: `amarela`, `bege`, `clara`, and `rosada`.

## 🚀 Features

* Automatic detection of Petri dish using Hough Circle Transform.
* Manual override for dish coordinates and radius (x, y, r).
* Classification of colonies based on color in HSV space.
* Advanced filtering by area, circularity, and maximum relative size to improve accuracy.
* Visualization output with colored circles indicating colony classification.
* 🔽 Download processed image with one click.
* 🧮 Summary output displayed: total colonies counted in the analyzed sub-area + breakdown by color.
* ♻️ "Nova Imagem" button resets interface for next upload.
* 📋 Response headers include detailed summary, filtering feedback, and calculated density/estimates.
* 🕒 Historical log of all analyses with:
    * Date, time, sample name.
    * Total counted, density (UFC/cm²), estimated total for a standard plate (57.5 cm²).
    * ⬜ Checkboxes to select rows.
    * ❌ Delete individual entries or 🗑️ "Excluir Tudo".
    * ⬇️ Export selected entries as CSV.
* 👨‍🔬 "Powered by Daniel Borges" badge displayed in UI footer.

## 📬 API Endpoint

### `POST /contar/`

**Description:** Count and classify colonies in a Petri dish image.

**Parameters:**

* `file` (form-data, required): Image of the Petri dish (`.jpg`, `.png`).
* `nome_amostra` (form-data, required): Name to identify the sample.
* `x` (form-data, optional): X-coordinate of the plate center (pixels in the original image). Auto-detected if not provided.
* `y` (form-data, optional): Y-coordinate of the plate center (pixels in the original image). Auto-detected if not provided.
* `r` (form-data, optional): Radius of the plate (pixels in the original image). Auto-detected if not provided.

**Response:**

* A JPEG image with annotated colony detections and a summary overlay.
* Response headers with detection summary and feedback, including:
    * `X-Resumo-Total`, `X-Resumo-Amarela`, `X-Resumo-Bege`, `X-Resumo-Clara`, `X-Resumo-Rosada` (counts for the analyzed sub-area).
    * `X-Feedback-Avaliadas` (total potential colonies evaluated).
    * `X-Feedback-Filtradas-Area` (colonies filtered by area thresholds).
    * `X-Feedback-Filtradas-Circularidade` (colonies filtered by circularity).
    * `X-Feedback-Filtradas-Tamanho-Maximo` (colonies filtered for being too large relative to the plate).
    * `X-Feedback-Desenhadas` (colonies actually counted and drawn).
    * `X-Feedback-Raio-Detectado-Px` (radius of the detected Petri dish in pixels).
    * `X-Feedback-Area-Amostrada-Cm2` (effective area in cm² of the sub-region analyzed).
    * `X-Feedback-Densidade-Colonias-Cm2` (calculated colony density in UFC/cm² for the full plate).
    * `X-Feedback-Estimativa-Total-Colonias` (estimated total colonies for a standard 57.5 cm² plate).

**Error Handling:**

* Returns 422 if no Petri dish is detected and no manual coordinates are provided.
* Returns 400 for issues like empty file or image decoding errors.
* Returns 500 for unexpected internal server errors.

## 📦 Requirements

```bash
pip install fastapi uvicorn opencv-python-headless numpy scipy python-multipart pandas
```

## 🛠️ Run Locally

```bash
uvicorn main:app --reload
```

Then open: `http://127.0.0.1:8000/docs` to interact with the API using Swagger UI.

## 💻 Frontend Setup

Node.js and npm are required. Run the following commands:

```bash
cd frontend
npm install
npm run build
```


## 📌 Update Notes

### Version 1.5.6 (UI + API)

*Refined Calculation Logic: Significantly improved accuracy and robustness of density and total colony estimation by correcting and detailing the area extrapolation methodology.
*Optimized Logging: Essential operational logs maintained for monitoring, while verbose debug logs have been cleaned up post-resolution of calculation issues.
*New Feedback Header: Introduced X-Feedback-Filtradas-Tamanho-Maximo to provide insight into colonies filtered due to excessive size relative to the Petri dish.
*Consistent use of specific internal variable names (e.g., r_detectado_placa, r_margem_calculada) for improved code clarity and maintenance.

## 🔮 Future Work

* [ ] 🖱️ Allow user to draw ROI (Region of Interest) manually on /docs interface.
* [ ] 🌈 Improve support for noisy backgrounds and complex lighting.
* [ ] 🤖 Train a ML model to further improve classification and segmentation.
* [x] 💾 Persistent local storage for historical analyses (e.g., using browser's localStorage).
* [ ] ⚙️ Consider making more image processing parameters (e.g., thresholds for area, circularity, max colony size factor) configurable via the API for advanced users.

---

## 📄 License

MIT License © 2025 Lucas Daniel Borges Lopes
