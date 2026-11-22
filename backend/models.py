"""backend/models.py - Core data schemas and contracts.

Defines Pydantic models for tables, column profiles, inferred relationships,
document metadata, section chunks, version families, and ingestion responses.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ColumnProfile(BaseModel):
    """Detailed profile of a single tabular column."""

    name: str
    data_type: str
    null_count: int
    null_pct: float
    distinct_count: int
    min_value: Any | None = None
    max_value: Any | None = None
    sample_values: list[Any] = Field(default_factory=list)


class InferredRelationship(BaseModel):
    """Inferred relationship between a foreign key and primary/unique key."""

    from_table: str
    from_column: str
    to_table: str
    to_column: str
    containment_ratio: float
    confidence: float
    status: str = "inferred"  # "inferred" or "declared"


class TableProfile(BaseModel):
    """Profile of an ingested relational table."""

    table_name: str
    row_count: int
    column_count: int
    columns: list[ColumnProfile]
    primary_key: str | None = None
    inferred_relationships: list[InferredRelationship] = Field(default_factory=list)


class SchemaCard(BaseModel):
    """Compact structured schema card presented to query agents."""

    tables: list[TableProfile]
    documentation_text: str | None = None
    markdown_summary: str


class DocumentChunk(BaseModel):
    """A structure-aware chunk of text from an ingested document."""

    chunk_id: str
    doc_sha256: str
    file_name: str
    section_title: str
    page_number: int | None = None  # 1-based page index for PDFs; None for DOCX/TXT
    content: str  # Verbatim content strictly preserved for quote verification
    token_count: int = 0


class DocumentDateResult(BaseModel):
    """Result of date extraction from document body and filename."""

    doc_date: str | None = None  # Normalized ISO date (YYYY-MM-DD)
    source: str = "undated"  # "body", "filename", or "undated"
    date_disagreement: bool = False
    body_date: str | None = None
    filename_date: str | None = None


class DocumentMetadata(BaseModel):
    """Extracted metadata for an ingested document."""

    file_name: str
    sha256: str
    doc_title: str
    version_family: str
    doc_date: str | None = None  # ISO format (YYYY-MM-DD)
    doc_date_source: str = "undated"  # "body", "filename", "undated"
    date_disagreement: bool = False
    page_count: int | None = None
    section_count: int = 0
    chunk_count: int = 0
    warnings: list[str] = Field(default_factory=list)


class IngestionFileError(BaseModel):
    """Details of a rejected or failed file upload."""

    file_name: str
    error: str
    reason: str = "validation_error"


class IngestionSummary(BaseModel):
    """Comprehensive summary returned after file ingestion."""

    tables: list[TableProfile] = Field(default_factory=list)
    documents: list[DocumentMetadata] = Field(default_factory=list)
    version_families: dict[str, list[str]] = Field(default_factory=dict)
    documentation_loaded: bool = False
    errors: list[IngestionFileError] = Field(default_factory=list)
    timestamp: str = ""


class ChatSession(BaseModel):
    """Chat session metadata."""

    chat_id: str
    title: str
    created_at: str
    updated_at: str


class ChatMessage(BaseModel):
    """Stored chat message."""

    message_id: str
    chat_id: str
    role: str
    content: str
    status: str = "completed"
    interpreted_as: str | None = None
    web_enabled: bool = False
    citations: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""


class MessageCreateRequest(BaseModel):
    """Request payload to send a message to a chat."""

    content: str
    web_enabled: bool = False


class ChatCreateRequest(BaseModel):
    """Request payload to create a new chat."""

    title: str = "New Chat"
