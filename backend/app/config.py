from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")
    database_url: str = "sqlite:///./roadvision.db"
    secret_key: str = "dev-only-change-me"
    model_path: str = "models/best.pt"
    confidence_threshold: float = 0.20
    iou_threshold: float = 0.70
    max_upload_size_mb: int = 100
    process_every_n_frames: int = 3
    cors_origins: str = "http://localhost:5173"
    demo_mode: bool = False
    upload_dir: Path = BASE_DIR / "uploads"
    results_dir: Path = BASE_DIR / "results"
    reports_dir: Path = BASE_DIR / "reports"

settings = Settings()
for directory in (settings.upload_dir, settings.results_dir, settings.reports_dir): directory.mkdir(parents=True, exist_ok=True)
