"""Core application configuration for TARA."""

from pathlib import Path
import os
# pyrefly: ignore [missing-import]
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent.parent
STORAGE_DIR = BASE_DIR / "storage"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def _load_env() -> None:
    candidates = [
        BASE_DIR / ".env",
        BASE_DIR / "backend" / ".env",
        Path.cwd() / ".env"
    ]
    for env_path in candidates:
        if env_path.exists():
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        key, val = line.split("=", 1)
                        key = key.strip()
                        val = val.strip().strip('"').strip("'")
                        os.environ[key] = val
            except Exception:
                pass


_load_env()

class Settings(BaseModel):
    project_name: str = "TARA — Tech-Architecture & Automated Review Assistant"
    api_prefix: str = "/api"
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    storage_dir: Path = STORAGE_DIR
    default_model: str = os.getenv("TARA_LLM_MODEL", "gemini-3.6-flash")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")

settings = Settings()
