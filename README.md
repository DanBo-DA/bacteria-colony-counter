# 🧫 Colony Counter API - README

## 📄 Description

This FastAPI-based application processes images of Petri dishes to count and classify bacterial colonies based on their shape and color. It uses image processing and segmentation techniques to detect colonies, and classifies them into four color categories: `amarela`, `bege`, `clara`, and `rosada`.

## 🚀 Features

* Automatic detection of Petri dish using Hough Circle Transform.
* Manual override for dish coordinates and radius (x, y, r).
* Optional advanced mode with on-image drawing to set manual center/radius and fine-tune filters.
* Dica: para definir manualmente a ROI, clique no centro da placa e arraste até a borda.
* Classification of colonies using a trained color model (fallback to HSV rules).
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
* `area_min` (form-data, optional): Minimum colony area in pixels. Default `4.0`.
* `circularidade_min` (form-data, optional): Minimum circularity. Default `0.30`.
* `max_colony_size_factor` (form-data, optional): Max relative radius of a colony compared to the plate margin. Default `0.2`.
  Use esses parâmetros para refinar a contagem em "Análise Avançada".

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
pip install fastapi uvicorn opencv-python-headless numpy scipy python-multipart pandas scikit-learn joblib
```

## 🏋️ Treinar Modelo de Cor

Forneça um CSV com as colunas `h`, `s`, `v` e `label` (uma das quatro cores).
Execute:

```bash
python scripts/train_color_model.py dados.csv backend/color_model.pkl
```

O arquivo `color_model.pkl` será carregado automaticamente pelo backend.

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

Create a `.env` file in the project root defining the API base URL:

```
VITE_API_URL=https://bacteria-colony-counter-production.up.railway.app
```

The frontend reads this variable using `import.meta.env.VITE_API_URL` to send requests.


## 📌 Update Notes

### Version 1.6.7 (UI + API)

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

## 🔄 Version Bumping

The repository provides a helper script at `scripts/bump_version.py` to keep the
API and frontend versions in sync. Running the script increments the version in
`frontend/package.json`, updates the `version` argument of the `FastAPI()`
instance in `backend/main.py`, and commits the changes with the message
`Bump version`.

Run it manually whenever you need to bump the version:

```bash
python scripts/bump_version.py
```

### Optional Git Hook

Enable the provided pre-commit hook to run the script automatically before every
commit:

```bash
git config core.hooksPath .githooks
```

With the hook enabled, each commit will first create a separate version bump
commit generated by the script.

---

## 📄 License

MIT License © 2025 Lucas Daniel Borges Lopes
