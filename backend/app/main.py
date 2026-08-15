import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database.database import Base, engine
from app.api.routes import router


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


# ============================================================
# DATABASE
# ============================================================

Base.metadata.create_all(bind=engine)


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="RoadVision AI",
    version="1.0.0",
    description="Road-damage inspection API",
)


# ============================================================
# CORS CONFIGURATION
# ============================================================

# Keep origins configured through the backend settings
configured_origins = [
    origin.strip()
    for origin in settings.cors_origins.split(",")
    if origin.strip()
]

# Production frontend + local development frontend
allowed_origins = list(
    dict.fromkeys(
        configured_origins
        + [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "https://roadvision-ai-1vf0.onrender.com",
        ]
    )
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# API ROUTES
# ============================================================

app.include_router(router)


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/api/health")
def health():
    detector = __import__(
        "app.api.routes",
        fromlist=["detector"],
    ).detector

    return {
        "status": "ok",
        "model_available": detector.available,
        "demo_mode": settings.demo_mode,
    }