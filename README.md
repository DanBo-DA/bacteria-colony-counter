# 🧫 Bacteria Colony Counter

A simple web app to automatically detect and count bacterial colonies in Petri dish images using FastAPI (backend with OpenCV) and React (frontend with Vite).

## 📦 Project Structure

```
📁 backend
├── main.py               # FastAPI server with OpenCV processing
├── requirements.txt      # Python dependencies

📁 frontend
├── index.html
├── package.json
├── vite.config.js
└── src/
    ├── App.jsx           # Main React component
    └── main.jsx          # Entry point
```

---

## 🚀 Features

- Upload a photo of a Petri dish
- Automatically detect colonies using image processing (OpenCV)
- Returns a processed image with red circles around each colony
- Counts colonies and displays result to user

---

## 🛠️ Installation & Usage

### Backend (FastAPI)
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend (React)
```bash
cd frontend
npm install
npm run dev
```

Make sure to update the backend URL in `App.jsx` to match your deployment address (e.g., Railway, local).

---

## 🌐 Deployment

- **Backend**: Deploy on [Railway](https://railway.app/) or [Render](https://render.com/)
- **Frontend**: Deploy on [Vercel](https://vercel.com/) or [Netlify](https://www.netlify.com/)

To embed in **Google Sites**, use the frontend Vercel link in an embed block.

---

## 📄 License

MIT License © 2025 Lucas Daniel Borges Lopes
