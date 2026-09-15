from pathlib import Path
from contextlib import asynccontextmanager
# pyrefly: ignore [missing-import]
from fastapi import FastAPI
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
# pyrefly: ignore [missing-import]
from fastapi.staticfiles import StaticFiles
# pyrefly: ignore [missing-import]
from fastapi.responses import FileResponse
from app.core.config import settings
from app.core.cleanup import start_cleanup_scheduler, stop_cleanup_scheduler
from app.api.sessions import router as sessions_router

BASE_DIR = Path(__file__).resolve().parent.parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "static"
ASSETS_DIR = BASE_DIR / "assets"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan management: initializes 24h TTL background scheduler on startup."""
    start_cleanup_scheduler()
    yield
    stop_cleanup_scheduler()


app = FastAPI(
    title="TARA Backend & Web IDE",
    description="Multi-Agent Software Consultancy & Automated Review Assistant",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS configuration for Web IDE frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static web assets & repository brand assets
if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(sessions_router, prefix=settings.api_prefix)


@app.get("/")
def serve_ide():
    """Serves the primary web-based IDE application."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {
        "service": "TARA Backend API",
        "status": "operational",
        "version": "0.1.0",
        "docs_url": "/docs"
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}
