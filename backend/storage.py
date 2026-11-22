"""backend/storage.py - SQLite metadata/FTS5 store and DuckDB tabular store.

Manages persistent SQLite for document chunks, full-text FTS5 BM25 index,
dense embeddings, chat histories, and DuckDB for relational tables with
dual read-write / read-only sandbox isolation (ADR-002).
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

import duckdb

if TYPE_CHECKING:
    from backend.models import DocumentChunk, DocumentMetadata

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
SQLITE_DB_PATH = DATA_DIR / "assistant.db"
DUCKDB_PATH = DATA_DIR / "tables.duckdb"


def ensure_storage_dirs() -> None:
    """Ensure data storage directory exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_sqlite_connection():
    """Context manager for SQLite database connection that commits and closes cleanly."""
    ensure_storage_dirs()
    conn = sqlite3.connect(str(SQLITE_DB_PATH))
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_sqlite_db() -> None:
    """Initialize SQLite tables and FTS5 full-text search indexes."""
    with get_sqlite_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS files (
                sha256 TEXT PRIMARY KEY,
                file_name TEXT NOT NULL,
                file_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                uploaded_at TEXT NOT NULL,
                doc_title TEXT NOT NULL,
                version_family TEXT NOT NULL,
                doc_date TEXT,
                doc_date_source TEXT NOT NULL,
                date_disagreement INTEGER NOT NULL DEFAULT 0,
                page_count INTEGER,
                section_count INTEGER NOT NULL DEFAULT 0,
                chunk_count INTEGER NOT NULL DEFAULT 0,
                warnings TEXT
            );

            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                file_sha256 TEXT NOT NULL,
                file_name TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                section_title TEXT NOT NULL,
                page_number INTEGER,
                content TEXT NOT NULL,
                token_count INTEGER NOT NULL DEFAULT 0,
                embedding BLOB,
                FOREIGN KEY (file_sha256) REFERENCES files(sha256) ON DELETE CASCADE
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                chunk_id UNINDEXED,
                file_sha256 UNINDEXED,
                file_name UNINDEXED,
                section_title,
                content,
                tokenize='porter unicode61'
            );

            CREATE TABLE IF NOT EXISTS documentation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT NOT NULL,
                content TEXT NOT NULL,
                uploaded_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chats (
                chat_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                title TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                message_id TEXT PRIMARY KEY,
                chat_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                citations TEXT,
                metadata TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (chat_id) REFERENCES chats(chat_id) ON DELETE CASCADE
            );
            """
        )


@contextmanager
def get_duckdb_write_connection():
    """Context manager for DuckDB write connection during ingestion."""
    ensure_storage_dirs()
    conn = duckdb.connect(str(DUCKDB_PATH), read_only=False)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_duckdb_read_connection():
    """Context manager for hardened read-only DuckDB connection (ADR-002, R-009)."""
    ensure_storage_dirs()
    if not DUCKDB_PATH.exists():
        # Touch empty file or connect in memory
        duckdb.connect(str(DUCKDB_PATH)).close()
    conn = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    try:
        # Layered hardening: disable external filesystem/network calls from SQL
        conn.execute("SET enable_external_access = false;")
        yield conn
    finally:
        conn.close()


def save_file_metadata(
    meta: DocumentMetadata, file_type: str, size_bytes: int, uploaded_at: str
) -> None:
    """Save or update document file metadata in SQLite."""
    with get_sqlite_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO files (
                sha256, file_name, file_type, size_bytes, uploaded_at,
                doc_title, version_family, doc_date, doc_date_source,
                date_disagreement, page_count, section_count, chunk_count, warnings
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                meta.sha256,
                meta.file_name,
                file_type,
                size_bytes,
                uploaded_at,
                meta.doc_title,
                meta.version_family,
                meta.doc_date,
                meta.doc_date_source,
                1 if meta.date_disagreement else 0,
                meta.page_count,
                meta.section_count,
                meta.chunk_count,
                json.dumps(meta.warnings),
            ),
        )


def save_chunks(chunks: list[DocumentChunk], embeddings: list[bytes] | None = None) -> None:
    """Store chunks and index them into FTS5."""
    with get_sqlite_connection() as conn:
        for idx, chunk in enumerate(chunks):
            emb_blob = embeddings[idx] if embeddings and idx < len(embeddings) else None
            conn.execute(
                """
                INSERT OR REPLACE INTO chunks (
                    chunk_id, file_sha256, file_name, chunk_index,
                    section_title, page_number, content, token_count, embedding
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk.chunk_id,
                    chunk.doc_sha256,
                    chunk.file_name,
                    idx,
                    chunk.section_title,
                    chunk.page_number,
                    chunk.content,
                    chunk.token_count,
                    emb_blob,
                ),
            )
            # Synchronize into FTS5 table
            conn.execute("DELETE FROM chunks_fts WHERE chunk_id = ?", (chunk.chunk_id,))
            conn.execute(
                """
                INSERT INTO chunks_fts (chunk_id, file_sha256, file_name, section_title, content)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    chunk.chunk_id,
                    chunk.doc_sha256,
                    chunk.file_name,
                    chunk.section_title,
                    chunk.content,
                ),
            )


def save_data_documentation(file_name: str, content: str, uploaded_at: str) -> None:
    """Store raw data dictionary text for SQL agent grounding (R-002)."""
    with get_sqlite_connection() as conn:
        conn.execute("DELETE FROM documentation WHERE file_name = ?", (file_name,))
        conn.execute(
            "INSERT INTO documentation (file_name, content, uploaded_at) VALUES (?, ?, ?)",
            (file_name, content, uploaded_at),
        )


def get_all_data_documentation() -> str:
    """Fetch all loaded data documentation texts."""
    init_sqlite_db()
    with get_sqlite_connection() as conn:
        rows = conn.execute("SELECT content FROM documentation ORDER BY id ASC").fetchall()
        return "\n\n---\n\n".join(r[0] for r in rows)


def get_file_by_sha256(sha256: str) -> dict[str, Any] | None:
    """Retrieve file record by SHA-256 for idempotency checks."""
    init_sqlite_db()
    with get_sqlite_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM files WHERE sha256 = ?", (sha256,))
        row = cur.fetchone()
        return dict(row) if row else None


def list_all_files() -> list[dict[str, Any]]:
    """List all ingested files with metadata."""
    init_sqlite_db()
    with get_sqlite_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM files ORDER BY doc_date DESC, file_name ASC")
        return [dict(r) for r in cur.fetchall()]


def reset_storage() -> None:
    """Reset all database tables without unlinking files to prevent Windows locking errors."""
    ensure_storage_dirs()
    init_sqlite_db()
    with get_sqlite_connection() as conn:
        conn.executescript(
            """
            DELETE FROM chunks_fts;
            DELETE FROM chunks;
            DELETE FROM files;
            DELETE FROM documentation;
            DELETE FROM messages;
            DELETE FROM chats;
            """
        )

    # Reset DuckDB tables
    if DUCKDB_PATH.exists():
        with get_duckdb_write_connection() as conn:
            try:
                tables = conn.execute("SHOW TABLES;").fetchall()
                for (t_name,) in tables:
                    conn.execute(f"DROP TABLE IF EXISTS {t_name};")
            except Exception:
                pass
