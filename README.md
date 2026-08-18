## 🌐 Live Project

🚀 [Open RoadVision AI](roadvision-ai.up.railway.app)

# RoadVision AI

RoadVision AI is a full-stack road-damage inspection workspace for images and browser-camera frames. It uses React/Vite, FastAPI, SQLAlchemy, OpenCV, ReportLab and a pluggable Ultralytics YOLO model. It does **not** claim accuracy or invent detections when trained model weights are absent.

## Features

- JWT registration/login with Argon2 password hashing
- Authenticated image and browser-camera inspection workflows
- Custom YOLO model wrapper, OpenCV annotation, configurable thresholds and CPU/GPU inference
- Transparent, pixel-relative severity estimate (not physical area)
- SQLite development persistence, PostgreSQL-ready configuration, inspection history and dashboard charts
- Downloadable PDF inspection reports and Docker development setup

## Quick start

Backend (Windows PowerShell):

```powershell
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

Frontend (a second terminal):

```powershell
cd frontend
npm install
npm run dev
```

Open the app at http://localhost:5173. The backend is http://localhost:8000 and Swagger is http://localhost:8000/docs.

## Model setup

Train or obtain an appropriately licensed, evaluated road-damage YOLO model whose class ordering matches [training/data.yaml](training/data.yaml). Place its weights at `backend/models/road_damage.pt`, then restart the backend. In the default no-model state, uploads still validate, annotate, store, and report—but contain zero detections by design. See [backend/models/README.md](backend/models/README.md).

## Training

Prepare the dataset layout documented in [docs/training.md](docs/training.md), install backend requirements, then run:

```powershell
python training/train.py --epochs 80 --batch 8 --imgsz 640
python training/validate.py
python training/export.py
```

## Testing and deployment

Run backend unit tests from `backend`: `pytest`. Start both services with `docker compose up --build`. For production, set a strong `SECRET_KEY`, a PostgreSQL `DATABASE_URL`, restrictive `CORS_ORIGINS`, persistent volumes/storage, and serve behind TLS.

## Limitations

Video processing samples frames at the configured interval and does not currently track the same defect across frames, so counts may include repeated observations. Camera analysis captures a frame on demand to keep normal laptops responsive. Severity estimates are not calibrated measurements. See [docs/architecture.md](docs/architecture.md) for architecture and [docs/api.md](docs/api.md) for endpoints.
