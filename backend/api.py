"""backend/api.py - FastAPI HTTP routes for upload and ingestion status.

Exposes endpoints for file uploads, schema card inspection,
and ingestion summaries with graceful JSON error responses.
"""

from __future__ import annotations

from fastapi import APIRouter, FastAPI, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from backend.ingestion import (
    _LOADED_TABLES,
    _TABLE_PROFILES,
    get_active_schema_card,
    get_current_ingestion_summary,
    ingest_files,
)
from backend.models import IngestionSummary
from backend.storage import init_sqlite_db, reset_storage

app = FastAPI(
    title="Multi-Source Assistant API",
    description="Backend API for tabular analysis and grounded document question answering",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

router = APIRouter(prefix="/api")


@router.get("/health")
def health_check() -> dict[str, str]:
    """Basic healthcheck endpoint."""
    return {"status": "ok"}


@router.post("/upload", response_model=IngestionSummary)
async def upload_files(files: list[UploadFile]) -> IngestionSummary:
    """Ingest one or more uploaded files (CSV, PDF, DOCX, TXT, MD)."""
    file_payloads: list[tuple[str, bytes]] = []
    for file in files:
        content = await file.read()
        file_payloads.append((file.filename or "uploaded_file", content))

    summary = ingest_files(file_payloads)
    return summary


@router.get("/ingestion-summary", response_model=IngestionSummary)
def get_summary() -> IngestionSummary:
    """Retrieve the current ingestion state across tables and documents."""
    return get_current_ingestion_summary()


@router.get("/schema-card")
def get_schema_card() -> dict[str, str]:
    """Retrieve markdown-formatted schema card with profiling and data dictionary definitions."""
    return {"schema_card": get_active_schema_card()}


@router.post("/reset")
def reset_database() -> dict[str, str]:
    """Reset persistent DuckDB and SQLite storage."""
    reset_storage()
    _LOADED_TABLES.clear()
    _TABLE_PROFILES.clear()
    return {"status": "cleared"}


app.include_router(router)


@app.on_event("startup")
def startup_event():
    """Initialize storage structures on service boot."""
    init_sqlite_db()
