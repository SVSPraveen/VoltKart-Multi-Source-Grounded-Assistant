"""backend/api.py - FastAPI HTTP routes for upload and ingestion status.

Exposes endpoints for file uploads, schema card inspection,
and ingestion summaries with graceful JSON error responses.
"""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.assistant import ask_assistant
from backend.export_pdf import generate_chat_pdf
from backend.ingestion import (
    _LOADED_TABLES,
    _TABLE_PROFILES,
    get_active_schema_card,
    get_current_ingestion_summary,
    ingest_files,
)
from backend.models import (
    ChatCreateRequest,
    ChatSession,
    IngestionSummary,
    MessageCreateRequest,
)
from backend.sql_sandbox import execute_sandboxed_query
from backend.storage import (
    create_chat,
    delete_chat,
    delete_file_by_sha256,
    get_chat,
    get_chat_messages,
    init_sqlite_db,
    list_all_files,
    list_chats,
    reset_storage,
    update_chat_title,
)


def validate_chat_id(chat_id: str) -> str:
    """Validate and sanitize chat_id to prevent injection and header manipulation."""
    if not chat_id or not re.match(r"^[a-zA-Z0-9_\-\.]{1,64}$", chat_id):
        raise HTTPException(status_code=400, detail="Invalid chat_id format")
    return chat_id


def validate_sha256(sha256: str) -> str:
    """Validate SHA-256 hash format."""
    if not sha256 or not re.match(r"^[a-fA-F0-9]{64}$", sha256):
        raise HTTPException(status_code=400, detail="Invalid SHA-256 hash format")
    return sha256.lower()


class QueryRequest(BaseModel):
    """User query request body."""

    question: str
    chat_id: str = "default"
    web_enabled: bool = False


class SQLExecuteRequest(BaseModel):
    """Raw sandboxed SQL execution request."""

    sql: str
    row_cap: int = 100


class ChatUpdateRequest(BaseModel):
    """Payload to update chat session metadata."""

    title: str


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


@router.post("/query")
def process_query(request: QueryRequest) -> dict[str, Any]:
    """Execute multi-source question answering pipeline."""
    clean_id = validate_chat_id(request.chat_id)
    return ask_assistant(
        question=request.question,
        chat_id=clean_id,
        web_enabled=request.web_enabled,
    )


@router.post("/execute-sql")
def execute_sql(request: SQLExecuteRequest) -> dict[str, Any]:
    """Execute raw SQL in hardened read-only sandbox for verification and auditing."""
    result = execute_sandboxed_query(request.sql, row_cap=request.row_cap)
    return result.to_dict()


@router.get("/files")
def get_all_files_endpoint() -> list[dict[str, Any]]:
    """Retrieve all ingested file records and version metadata."""
    return list_all_files()


@router.delete("/files/{sha256}")
def delete_file_endpoint(sha256: str) -> dict[str, str]:
    """Delete an ingested file by its SHA-256 hash."""
    clean_sha = validate_sha256(sha256)
    success = delete_file_by_sha256(clean_sha)
    if not success:
        raise HTTPException(status_code=404, detail="File not found")
    return {"status": "deleted", "sha256": clean_sha}


@router.get("/chats", response_model=list[ChatSession])
def list_chats_endpoint() -> list[dict[str, Any]]:
    """List all chat sessions ordered by last activity."""
    return list_chats()


@router.post("/chats", response_model=ChatSession)
def create_chat_endpoint(request: ChatCreateRequest | None = None) -> dict[str, Any]:
    """Create a new chat conversation."""
    new_chat_id = f"chat_{uuid.uuid4().hex[:8]}"
    title = request.title if request and request.title else "New Chat"
    return create_chat(new_chat_id, title=title)


@router.get("/chats/{chat_id}", response_model=ChatSession)
def get_chat_endpoint(chat_id: str) -> dict[str, Any]:
    """Get metadata for a specific chat."""
    clean_id = validate_chat_id(chat_id)
    info = get_chat(clean_id)
    if not info:
        raise HTTPException(status_code=404, detail="Chat not found")
    return info


@router.delete("/chats/{chat_id}")
def delete_chat_endpoint(chat_id: str) -> dict[str, str]:
    """Delete a chat and its message history."""
    clean_id = validate_chat_id(chat_id)
    success = delete_chat(clean_id)
    if not success:
        raise HTTPException(status_code=404, detail="Chat not found")
    return {"status": "deleted", "chat_id": clean_id}


@router.patch("/chats/{chat_id}", response_model=ChatSession)
def update_chat_endpoint(chat_id: str, request: ChatUpdateRequest) -> dict[str, Any]:
    """Update title of an existing chat session."""
    clean_id = validate_chat_id(chat_id)
    update_chat_title(clean_id, request.title)
    info = get_chat(clean_id)
    if not info:
        raise HTTPException(status_code=404, detail="Chat not found")
    return info


@router.post("/chats/{chat_id}/messages")
async def send_message_stream(chat_id: str, request: MessageCreateRequest):
    """Server-Sent Events (SSE) streaming API for chat message generation (C1, ADR-005).

    Streams live pipeline status events during reasoning and verification,
    followed by the final grounded answer and structured citations.
    """
    clean_id = validate_chat_id(chat_id)

    async def event_generator():
        try:
            # 1. Pipeline status: Initializing retrieval and schema inspection
            status1 = json.dumps({"status": "Searching documents and database schemas..."})
            yield f"event: status\ndata: {status1}\n\n"
            await asyncio.sleep(0.04)

            # 2. Pipeline status: Tool execution
            status2 = json.dumps(
                {"status": "Executing analytical SQL and retrieving source chunks..."}
            )
            yield f"event: status\ndata: {status2}\n\n"
            await asyncio.sleep(0.04)

            # Execute multi-source QA pipeline
            response = ask_assistant(
                question=request.content,
                chat_id=clean_id,
                web_enabled=request.web_enabled,
            )

            # 3. Pipeline status: Verification
            status3 = json.dumps({"status": "Verifying citations and numeric grounding..."})
            yield f"event: status\ndata: {status3}\n\n"
            await asyncio.sleep(0.04)

            # 4. Stream verified citations
            for cit in response.get("citations", []):
                yield f"event: citation\ndata: {json.dumps(cit)}\n\n"

            # 4b. Stream verified analytical chart specs (B10, spec 7.8)
            for ch in response.get("charts", []):
                yield f"event: chart\ndata: {json.dumps(ch)}\n\n"

            # 5. Stream verified answer content
            answer_payload = {
                "content": response.get("answer", ""),
                "interpreted_as": response.get("interpreted_as"),
                "abstained": response.get("abstained", False),
                "citations": response.get("citations", []),
                "charts": response.get("charts", []),
            }
            yield f"event: answer\ndata: {json.dumps(answer_payload)}\n\n"

            # 6. Stream done event
            yield f"event: done\ndata: {json.dumps({'status': 'completed', 'chat_id': clean_id})}\n\n"

        except Exception as exc:
            yield f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/chats/{chat_id}/export.pdf")
def export_chat_pdf_endpoint(chat_id: str):
    """Export conversation history as an auditable PDF document with embedded ₹ font (C7, ADR-006)."""
    clean_id = validate_chat_id(chat_id)
    pdf_bytes = generate_chat_pdf(clean_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="chat_{clean_id}_export.pdf"',
        },
    )


@router.get("/chats/{chat_id}/messages")
def get_messages(chat_id: str) -> dict[str, Any]:
    """Retrieve message history for a specific chat."""
    clean_id = validate_chat_id(chat_id)
    msgs = get_chat_messages(clean_id)
    return {"chat_id": clean_id, "messages": msgs}


@router.post("/reset")
def reset_database() -> dict[str, str]:
    """Reset persistent DuckDB and SQLite storage."""
    reset_storage()
    _LOADED_TABLES.clear()
    _TABLE_PROFILES.clear()
    return {"status": "cleared"}


app.include_router(router)

# Mount compiled frontend static build if present
DIST_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if DIST_DIR.exists():
    app.mount("/", StaticFiles(directory=str(DIST_DIR), html=True), name="frontend")


@app.on_event("startup")
def startup_event():
    """Initialize storage structures on service boot."""
    init_sqlite_db()
