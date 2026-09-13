"""Main FastAPI application entry point for TARA."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.sessions import router as sessions_router

app = FastAPI(
    title="TARA Backend Service",
    description="Multi-Agent Software Consultancy & Automated Review Assistant",
    version="0.1.0"
)

# CORS configuration for Web IDE frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins in development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions_router, prefix=settings.api_prefix)


@app.get("/")
def root():
    return {
        "service": "TARA Backend API",
        "status": "operational",
        "version": "0.1.0",
        "docs_url": "/docs"
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}
