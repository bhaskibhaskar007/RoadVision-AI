import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database.database import Base, engine
from app.api.routes import router
logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(name)s %(message)s")
Base.metadata.create_all(bind=engine)
app=FastAPI(title="RoadVision AI",version="1.0.0",description="Road-damage inspection API")
app.add_middleware(CORSMiddleware,allow_origins=[x.strip() for x in settings.cors_origins.split(',')],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
app.include_router(router)
@app.get("/api/health")
def health(): return {"status":"ok","model_available":__import__('app.api.routes',fromlist=['detector']).detector.available,"demo_mode":settings.demo_mode}
