from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.convert import router as convert_router
from app.api.download import router as download_router
from app.api.formats import router as formats_router
from app.api.params import router as params_router
from app.api.task import router as task_router
from app.api.upload import router as upload_router
from app.core.config import settings
from app.core.database import create_tables
from app.core.storage import ensure_upload_dir


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup / shutdown."""
    # Startup
    await ensure_upload_dir()
    await create_tables()
    yield
    # Shutdown — cleanup if needed


app = FastAPI(
    title="PDF Editing & Conversion Platform",
    description="REST API for converting and editing PDF documents",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────
app.include_router(upload_router, prefix="/api/v1", tags=["Upload"])
app.include_router(formats_router, prefix="/api/v1", tags=["Formats"])
app.include_router(params_router, prefix="/api/v1", tags=["Parameters"])
app.include_router(convert_router, prefix="/api/v1", tags=["Conversion"])
app.include_router(task_router, prefix="/api/v1", tags=["Tasks"])
app.include_router(download_router, prefix="/api/v1", tags=["Download"])


# ── Health ───────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "version": "0.1.0"}
