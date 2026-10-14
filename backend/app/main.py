from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.datasets import router as datasets_router
from app.api.pipelines import router as pipelines_router
from app.api.projects import router as projects_router
from app.core.config import settings
from app.database import Base, engine

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="MavuFlow Studio API for data engineering workflows.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)
app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(datasets_router)
app.include_router(pipelines_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
    }


@app.get("/api/v1/health")
def api_health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "api": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
    }
