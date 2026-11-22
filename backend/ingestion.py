"""backend/ingestion.py - Orchestrator for multi-source ingestion and storage.

Processes uploaded CSV tables and documents, enforces idempotency via SHA-256,
handles all edge cases gracefully per REVIEW R-023, and produces structured
ingestion summaries for users and agents.
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from backend.documents import chunk_document
from backend.embeddings import embed_batch, serialize_vector
from backend.models import (
    DocumentMetadata,
    IngestionFileError,
    IngestionSummary,
    TableProfile,
)
from backend.storage import (
    get_all_data_documentation,
    get_file_by_sha256,
    init_sqlite_db,
    list_all_files,
    load_all_table_profiles,
    register_reset_callback,
    save_chunks,
    save_data_documentation,
    save_file_metadata,
    save_table_profile,
)
from backend.tables import (
    generate_schema_card,
    infer_foreign_keys,
    ingest_table,
    is_data_documentation_text,
    parse_declared_schema_from_documentation,
)

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
OLE_DOC_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
PDF_MAGIC = b"%PDF-"
ZIP_DOCX_MAGIC = b"PK\x03\x04"

# In-memory registry of loaded table DataFrames and profiles during application lifecycle
_LOADED_TABLES: dict[str, pd.DataFrame] = {}
_TABLE_PROFILES: dict[str, TableProfile] = {}


def _clear_in_memory_cache() -> None:
    _LOADED_TABLES.clear()
    _TABLE_PROFILES.clear()


register_reset_callback(_clear_in_memory_cache)


def sanitize_filename(raw_filename: str) -> str:
    """Sanitize filename to prevent cross-platform directory traversal attacks (R-023)."""
    # Remove null bytes and control chars
    clean = re.sub(r"[\x00-\x1f\x7f]", "", raw_filename)
    # Normalize path separators across OS
    clean = clean.replace("\\", "/")
    # Extract only the base filename
    base_name = clean.split("/")[-1].strip()
    # Strip dangerous characters
    base_name = re.sub(r'["\'<>|?*:]', "", base_name)
    return base_name or "uploaded_file"


def validate_file_content(filename: str, content: bytes) -> None:
    """Perform fast security and format validation against R-023 upload edge cases."""
    if len(content) == 0:
        raise ValueError(f"File '{filename}' is empty (0 bytes)")

    if len(content) > MAX_FILE_SIZE_BYTES:
        raise ValueError(
            f"File '{filename}' exceeds maximum allowed size of {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB"
        )

    ext = Path(filename).suffix.lower()

    # Legacy .doc rejection
    if ext == ".doc" or (len(content) >= 8 and content[:8] == OLE_DOC_MAGIC):
        raise ValueError(
            f"File '{filename}' is in legacy .doc format. Please convert to .docx or PDF."
        )

    # Magic byte validation for binary formats
    if ext == ".pdf":
        if not content.startswith(PDF_MAGIC):
            raise ValueError(
                f"File '{filename}' has .pdf extension but does not contain valid PDF headers"
            )

    if ext == ".docx":
        if not content.startswith(ZIP_DOCX_MAGIC):
            raise ValueError(
                f"File '{filename}' has .docx extension but is not a valid Office Open XML zip file"
            )
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                namelist = zf.namelist()
                if not any("word/" in n or "[Content_Types].xml" in n for n in namelist):
                    raise ValueError(
                        f"File '{filename}' is a zip archive but not a valid Word (.docx) document"
                    )
        except zipfile.BadZipFile as exc:
            raise ValueError(f"File '{filename}' is a corrupted zip archive") from exc


def process_single_file(
    filename: str,
    content: bytes,
) -> tuple[str, Any]:
    """Process a single uploaded file (table, document, or documentation) returning (type, result)."""
    clean_name = sanitize_filename(filename)
    validate_file_content(clean_name, content)

    file_sha256 = hashlib.sha256(content).hexdigest()
    now_utc = datetime.now(UTC).isoformat()
    ext = Path(clean_name).suffix.lower()

    if ext == ".csv":
        # Relational tabular data
        tbl_name, df, profile = ingest_table(content, clean_name)
        _LOADED_TABLES[tbl_name] = df
        _TABLE_PROFILES[tbl_name] = profile

        # Check if data documentation has declared schema keys (spec 7.1)
        doc_text = get_all_data_documentation()
        declared_pks, declared_fks = parse_declared_schema_from_documentation(doc_text)
        if tbl_name in declared_pks:
            profile.primary_key = declared_pks[tbl_name]

        # Update relationships across all known tables
        pks = {name: prof.primary_key for name, prof in _TABLE_PROFILES.items()}
        all_rels = infer_foreign_keys(_LOADED_TABLES, pks, declared_fks)
        for name, prof in _TABLE_PROFILES.items():
            prof.inferred_relationships = [r for r in all_rels if r.from_table == name]
            save_table_profile(prof, now_utc)

        return "table", profile

    if ext in {".pdf", ".docx", ".txt", ".md"}:
        # Check if text is data documentation / dictionary text
        sample_text = content[:16384].decode("utf-8", errors="replace")
        known_tables = list(_LOADED_TABLES.keys())
        known_cols = [c.name for prof in _TABLE_PROFILES.values() for c in prof.columns]
        is_doc = is_data_documentation_text(
            sample_text, known_tables, known_cols, filename=clean_name
        )

        if ext in {".md", ".txt"} and is_doc:
            full_text = content.decode("utf-8", errors="replace")
            save_data_documentation(clean_name, full_text, now_utc)

            # Update declared schema across any already-loaded tables
            declared_pks, declared_fks = parse_declared_schema_from_documentation(full_text)
            for t_name, dec_pk in declared_pks.items():
                if t_name in _TABLE_PROFILES:
                    _TABLE_PROFILES[t_name].primary_key = dec_pk

            pks = {name: prof.primary_key for name, prof in _TABLE_PROFILES.items()}
            all_rels = infer_foreign_keys(_LOADED_TABLES, pks, declared_fks)
            for name, prof in _TABLE_PROFILES.items():
                prof.inferred_relationships = [r for r in all_rels if r.from_table == name]
                save_table_profile(prof, now_utc)

            return "documentation", clean_name

        # Check for idempotency on standard knowledge base documents
        existing = get_file_by_sha256(file_sha256)
        if existing:
            meta = DocumentMetadata(
                file_name=clean_name,
                sha256=file_sha256,
                doc_title=existing["doc_title"],
                version_family=existing["version_family"],
                doc_date=existing["doc_date"],
                doc_date_source=existing["doc_date_source"],
                date_disagreement=bool(existing["date_disagreement"]),
                page_count=existing["page_count"],
                section_count=existing["section_count"],
                chunk_count=existing["chunk_count"],
                warnings=[],
            )
            return "document", meta

        # Structure-aware extraction and chunking
        metadata, chunks = chunk_document(content, clean_name, file_sha256)

        # Generate local dense embeddings
        chunk_texts = [f"{c.section_title}\n{c.content}" for c in chunks]
        vectors = embed_batch(chunk_texts)
        emb_blobs = [serialize_vector(v) for v in vectors]

        # Persist chunks and SQLite metadata
        save_file_metadata(metadata, ext[1:], len(content), now_utc)
        save_chunks(chunks, emb_blobs)

        return "document", metadata

    raise ValueError(f"Unsupported file extension '{ext}'. Allowed: .csv, .pdf, .docx, .txt, .md")


def ingest_files(files: list[tuple[str, bytes]]) -> IngestionSummary:
    """Ingest a batch of files and return a comprehensive summary."""
    init_sqlite_db()
    errors: list[IngestionFileError] = []

    # First pass: Ingest all CSV tables so schema columns are known for doc detection
    csv_files = [f for f in files if Path(f[0]).suffix.lower() == ".csv"]
    doc_files = [f for f in files if Path(f[0]).suffix.lower() != ".csv"]

    for name, content in csv_files:
        try:
            process_single_file(name, content)
        except Exception as exc:
            errors.append(IngestionFileError(file_name=name, error=str(exc)))

    # Second pass: Ingest documents (PDF, DOCX, TXT, MD)
    for name, content in doc_files:
        try:
            process_single_file(name, content)
        except Exception as exc:
            errors.append(IngestionFileError(file_name=name, error=str(exc)))

    return get_current_ingestion_summary(errors=errors)


def get_current_ingestion_summary(
    errors: list[IngestionFileError] | None = None,
) -> IngestionSummary:
    """Construct full ingestion summary from SQLite metadata and DuckDB tables."""
    init_sqlite_db()
    raw_files = list_all_files()

    docs: list[DocumentMetadata] = []
    families: dict[str, list[str]] = {}

    for rf in raw_files:
        meta = DocumentMetadata(
            file_name=rf["file_name"],
            sha256=rf["sha256"],
            doc_title=rf["doc_title"],
            version_family=rf["version_family"],
            doc_date=rf["doc_date"],
            doc_date_source=rf["doc_date_source"],
            date_disagreement=bool(rf["date_disagreement"]),
            page_count=rf["page_count"],
            section_count=rf["section_count"],
            chunk_count=rf["chunk_count"],
            warnings=[],
        )
        docs.append(meta)
        fam = rf["version_family"]
        families.setdefault(fam, []).append(rf["file_name"])

    # Load persistent table profiles from SQLite table_meta (spec sec 8)
    saved_profiles = load_all_table_profiles()
    for prof in saved_profiles:
        if prof.table_name not in _TABLE_PROFILES:
            _TABLE_PROFILES[prof.table_name] = prof

    tables_list = list(_TABLE_PROFILES.values()) if _TABLE_PROFILES else saved_profiles
    doc_text = get_all_data_documentation()

    return IngestionSummary(
        tables=tables_list,
        documents=docs,
        version_families=families,
        documentation_loaded=bool(doc_text.strip()),
        errors=errors or [],
        timestamp=datetime.now(UTC).isoformat(),
    )


def get_active_schema_card() -> str:
    """Return the formatted markdown schema card for the query engine."""
    summary = get_current_ingestion_summary()
    doc_text = get_all_data_documentation()
    card = generate_schema_card(summary.tables, doc_text)
    return card.markdown_summary
