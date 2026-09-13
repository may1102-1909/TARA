"""Core application configuration for TARA."""

from pathlib import Path
import os
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent.parent
STORAGE_DIR = BASE_DIR / "storage"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

class Settings(BaseModel):
    project_name: str = "TARA — Tech-Architecture & Automated Review Assistant"
    api_prefix: str = "/api"
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    storage_dir: Path = STORAGE_DIR
    default_model: str = os.getenv("TARA_LLM_MODEL", "gemini-2.5-flash")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")

settings = Settings()
