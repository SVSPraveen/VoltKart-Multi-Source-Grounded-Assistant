"""backend/storage.py - SQLite metadata/FTS5 store and DuckDB tabular store.

Manages persistent SQLite for document chunks, full-text FTS5 BM25 index,
dense embeddings, chat histories, and DuckDB for relational tables with
dual read-write / read-only sandbox isolation (ADR-002).
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

import duckdb

from backend.models import ColumnProfile, InferredRelationship, TableProfile

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
                status TEXT NOT NULL DEFAULT 'completed',
                interpreted_as TEXT,
                web_enabled INTEGER NOT NULL DEFAULT 0,
                citations TEXT,
                charts TEXT,
                metadata TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (chat_id) REFERENCES chats(chat_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS table_meta (
                table_name TEXT PRIMARY KEY,
                row_count INTEGER NOT NULL,
                column_count INTEGER NOT NULL,
                primary_key TEXT,
                columns_json TEXT NOT NULL,
                relationships_json TEXT NOT NULL,
                uploaded_at TEXT NOT NULL
            );
            """
        )

        # Migrations for existing tables if needed
        for col_name, col_def in [
            ("status", "TEXT NOT NULL DEFAULT 'completed'"),
            ("interpreted_as", "TEXT"),
            ("web_enabled", "INTEGER NOT NULL DEFAULT 0"),
            ("charts", "TEXT"),
        ]:
            try:
                conn.execute(f"ALTER TABLE messages ADD COLUMN {col_name} {col_def};")
            except sqlite3.OperationalError:
                pass


def ensure_chat_exists(chat_id: str, title: str = "New Chat") -> None:
    """Ensure a chat row exists in SQLite for foreign key constraints."""
    init_sqlite_db()
    with get_sqlite_connection() as conn:
        now = time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime())
        conn.execute(
            """
            INSERT OR IGNORE INTO chats (chat_id, created_at, updated_at, title)
            VALUES (?, ?, ?, ?)
            """,
            (chat_id, now, now, title),
        )


def create_chat(chat_id: str, title: str = "New Chat") -> dict[str, Any]:
    """Create a new chat session."""
    init_sqlite_db()
    now = time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime())
    with get_sqlite_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO chats (chat_id, created_at, updated_at, title)
            VALUES (?, ?, ?, ?)
            """,
            (chat_id, now, now, title),
        )
    return {"chat_id": chat_id, "title": title, "created_at": now, "updated_at": now}


def list_chats() -> list[dict[str, Any]]:
    """List all chat sessions ordered by last updated."""
    init_sqlite_db()
    with get_sqlite_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM chats ORDER BY updated_at DESC")
        return [dict(r) for r in cur.fetchall()]


def get_chat(chat_id: str) -> dict[str, Any] | None:
    """Retrieve metadata for a specific chat."""
    init_sqlite_db()
    with get_sqlite_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM chats WHERE chat_id = ?", (chat_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def update_chat_title(chat_id: str, title: str) -> None:
    """Update title of a chat session."""
    init_sqlite_db()
    now = time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime())
    with get_sqlite_connection() as conn:
        conn.execute(
            "UPDATE chats SET title = ?, updated_at = ? WHERE chat_id = ?",
            (title, now, chat_id),
        )


def delete_chat(chat_id: str) -> bool:
    """Delete a chat and all its messages."""
    init_sqlite_db()
    with get_sqlite_connection() as conn:
        cur = conn.execute("DELETE FROM chats WHERE chat_id = ?", (chat_id,))
        return cur.rowcount > 0


def save_message(
    message_id: str,
    chat_id: str,
    role: str,
    content: str,
    citations: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
    status: str = "completed",
    interpreted_as: str | None = None,
    web_enabled: bool = False,
    charts: list[dict[str, Any]] | None = None,
) -> None:
    """Persist a chat message with citations, charts, status, and metadata."""
    init_sqlite_db()
    ensure_chat_exists(chat_id)
    with get_sqlite_connection() as conn:
        now = time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime())
        conn.execute(
            """
            INSERT INTO messages (
                message_id, chat_id, role, content, status,
                interpreted_as, web_enabled, citations, charts, metadata, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message_id,
                chat_id,
                role,
                content,
                status,
                interpreted_as,
                1 if web_enabled else 0,
                json.dumps(citations or []),
                json.dumps(charts or []),
                json.dumps(metadata or {}),
                now,
            ),
        )
        if role == "user":
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                "SELECT title, (SELECT COUNT(*) FROM messages WHERE chat_id = ? AND role = 'user') as ucnt FROM chats WHERE chat_id = ?",
                (chat_id, chat_id),
            )
            row = cur.fetchone()
            if (
                row
                and row["ucnt"] <= 1
                and (row["title"] in ("New Chat", "New Conversation", "") or not row["title"])
            ):
                first_line = content.strip().split("\n")[0].strip()
                clean_title = first_line[:42] + ("..." if len(first_line) > 42 else "")
                conn.execute(
                    "UPDATE chats SET title = ?, updated_at = ? WHERE chat_id = ?",
                    (clean_title, now, chat_id),
                )
            else:
                conn.execute("UPDATE chats SET updated_at = ? WHERE chat_id = ?", (now, chat_id))
        else:
            conn.execute("UPDATE chats SET updated_at = ? WHERE chat_id = ?", (now, chat_id))


def update_message(
    message_id: str,
    content: str | None = None,
    status: str | None = None,
    interpreted_as: str | None = None,
    citations: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
    charts: list[dict[str, Any]] | None = None,
) -> None:
    """Update an existing message's content, status, citations, charts, or metadata."""
    init_sqlite_db()
    updates: list[str] = []
    params: list[Any] = []
    if content is not None:
        updates.append("content = ?")
        params.append(content)
    if status is not None:
        updates.append("status = ?")
        params.append(status)
    if interpreted_as is not None:
        updates.append("interpreted_as = ?")
        params.append(interpreted_as)
    if citations is not None:
        updates.append("citations = ?")
        params.append(json.dumps(citations))
    if charts is not None:
        updates.append("charts = ?")
        params.append(json.dumps(charts))
    if metadata is not None:
        updates.append("metadata = ?")
        params.append(json.dumps(metadata))

    if not updates:
        return

    params.append(message_id)
    with get_sqlite_connection() as conn:
        conn.execute(
            f"UPDATE messages SET {', '.join(updates)} WHERE message_id = ?", tuple(params)
        )


def get_chat_messages(chat_id: str) -> list[dict[str, Any]]:
    """Retrieve message history for a specific chat_id (R-012 scoped)."""
    init_sqlite_db()
    with get_sqlite_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT * FROM messages WHERE chat_id = ? ORDER BY rowid ASC",
            (chat_id,),
        )
        messages = []
        for r in cur.fetchall():
            m = dict(r)
            m["citations"] = json.loads(m["citations"]) if m.get("citations") else []
            m["charts"] = json.loads(m["charts"]) if m.get("charts") else []
            m["metadata"] = json.loads(m["metadata"]) if m.get("metadata") else {}
            m["web_enabled"] = bool(m.get("web_enabled", 0))
            messages.append(m)
        return messages


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


def delete_file_by_sha256(sha256: str) -> bool:
    """Delete a file and its associated chunks from SQLite and DuckDB if tabular."""
    init_sqlite_db()
    with get_sqlite_connection() as conn:
        row = conn.execute(
            "SELECT file_name, file_type FROM files WHERE sha256 = ?", (sha256,)
        ).fetchone()
        if not row:
            return False
        file_name = row[0]

        conn.execute("DELETE FROM chunks_fts WHERE file_sha256 = ?", (sha256,))
        conn.execute("DELETE FROM chunks WHERE file_sha256 = ?", (sha256,))
        conn.execute("DELETE FROM files WHERE sha256 = ?", (sha256,))

    if file_name.lower().endswith(".csv"):
        tbl_name = Path(file_name).stem.lower().replace("-", "_").replace(" ", "_")
        delete_table_profile(tbl_name)
        if DUCKDB_PATH.exists():
            with get_duckdb_write_connection() as duck_conn:
                try:
                    duck_conn.execute(f'DROP TABLE IF EXISTS "{tbl_name}";')
                except Exception:
                    pass
    return True


def save_table_profile(profile: TableProfile, uploaded_at: str) -> None:
    """Persist table metadata, column profiles, and relationships in SQLite table_meta (spec sec 8)."""
    init_sqlite_db()
    columns_json = json.dumps([col.model_dump() for col in profile.columns])
    relationships_json = json.dumps([rel.model_dump() for rel in profile.inferred_relationships])

    with get_sqlite_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO table_meta (
                table_name, row_count, column_count, primary_key,
                columns_json, relationships_json, uploaded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile.table_name,
                profile.row_count,
                profile.column_count,
                profile.primary_key,
                columns_json,
                relationships_json,
                uploaded_at,
            ),
        )


def load_all_table_profiles() -> list[TableProfile]:
    """Retrieve all persisted table profiles from SQLite table_meta."""
    init_sqlite_db()
    with get_sqlite_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM table_meta ORDER BY table_name ASC").fetchall()
        profiles: list[TableProfile] = []
        for r in rows:
            cols = [ColumnProfile(**c) for c in json.loads(r["columns_json"])]
            rels = [InferredRelationship(**rel) for rel in json.loads(r["relationships_json"])]
            profiles.append(
                TableProfile(
                    table_name=r["table_name"],
                    row_count=r["row_count"],
                    column_count=r["column_count"],
                    columns=cols,
                    primary_key=r["primary_key"],
                    inferred_relationships=rels,
                )
            )
        return profiles


def delete_table_profile(table_name: str) -> None:
    """Delete a table profile from SQLite table_meta."""
    init_sqlite_db()
    with get_sqlite_connection() as conn:
        conn.execute("DELETE FROM table_meta WHERE table_name = ?", (table_name,))


def search_chunks_fts(query: str, limit: int = 20) -> list[dict[str, Any]]:
    """Search chunks via SQLite FTS5 BM25 index across all document versions."""
    init_sqlite_db()
    tokens = re.findall(r"\w+", query)
    if not tokens:
        return []

    # Format tokens for safe FTS5 MATCH
    match_query = " OR ".join(f'"{t}"' for t in tokens if len(t) > 1)
    if not match_query:
        match_query = " OR ".join(f'"{t}"' for t in tokens)

    with get_sqlite_connection() as conn:
        conn.row_factory = sqlite3.Row
        sql = """
        SELECT c.chunk_id, c.file_sha256, c.file_name, c.chunk_index,
               c.section_title, c.page_number, c.content, c.token_count,
               f.version_family, f.doc_date, f.doc_title,
               bm25(chunks_fts) as rank
        FROM chunks_fts
        JOIN chunks c ON chunks_fts.chunk_id = c.chunk_id
        JOIN files f ON c.file_sha256 = f.sha256
        WHERE chunks_fts MATCH ?
        ORDER BY rank ASC
        LIMIT ?
        """
        cur = conn.execute(sql, (match_query, limit))
        return [dict(r) for r in cur.fetchall()]


def get_all_chunks_with_embeddings() -> list[dict[str, Any]]:
    """Retrieve all chunks that have dense vector embeddings along with file metadata."""
    init_sqlite_db()
    with get_sqlite_connection() as conn:
        conn.row_factory = sqlite3.Row
        sql = """
        SELECT c.chunk_id, c.file_sha256, c.file_name, c.chunk_index,
               c.section_title, c.page_number, c.content, c.token_count,
               c.embedding, f.version_family, f.doc_date, f.doc_title
        FROM chunks c
        JOIN files f ON c.file_sha256 = f.sha256
        WHERE c.embedding IS NOT NULL
        ORDER BY c.file_name ASC, c.chunk_index ASC
        """
        cur = conn.execute(sql)
        return [dict(r) for r in cur.fetchall()]


def get_chunks_for_family(version_family: str) -> list[dict[str, Any]]:
    """Retrieve all chunks for all versions in a given document family."""
    init_sqlite_db()
    with get_sqlite_connection() as conn:
        conn.row_factory = sqlite3.Row
        sql = """
        SELECT c.chunk_id, c.file_sha256, c.file_name, c.chunk_index,
               c.section_title, c.page_number, c.content, c.token_count,
               f.version_family, f.doc_date, f.doc_title
        FROM chunks c
        JOIN files f ON c.file_sha256 = f.sha256
        WHERE LOWER(f.version_family) = LOWER(?)
        ORDER BY f.doc_date ASC, c.chunk_index ASC
        """
        cur = conn.execute(sql, (version_family,))
        return [dict(r) for r in cur.fetchall()]


def get_files_for_family(version_family: str) -> list[dict[str, Any]]:
    """Retrieve all file metadata records in a given document family ordered chronologically."""
    init_sqlite_db()
    with get_sqlite_connection() as conn:
        conn.row_factory = sqlite3.Row
        sql = """
        SELECT * FROM files
        WHERE LOWER(version_family) = LOWER(?)
        ORDER BY doc_date ASC, file_name ASC
        """
        cur = conn.execute(sql, (version_family,))
        return [dict(r) for r in cur.fetchall()]


def get_chunks_by_file_name(file_name: str) -> list[dict[str, Any]]:
    """Retrieve all chunks for a specific document file."""
    init_sqlite_db()
    with get_sqlite_connection() as conn:
        conn.row_factory = sqlite3.Row
        sql = """
        SELECT c.chunk_id, c.file_sha256, c.file_name, c.chunk_index,
               c.section_title, c.page_number, c.content, c.token_count,
               f.version_family, f.doc_date, f.doc_title
        FROM chunks c
        JOIN files f ON c.file_sha256 = f.sha256
        WHERE c.file_name = ?
        ORDER BY c.chunk_index ASC
        """
        cur = conn.execute(sql, (file_name,))
        return [dict(r) for r in cur.fetchall()]


_ON_RESET_CALLBACKS: list[Any] = []


def register_reset_callback(cb: Any) -> None:
    """Register a callback to be called on storage reset (e.g. clearing in-memory caches)."""
    if cb not in _ON_RESET_CALLBACKS:
        _ON_RESET_CALLBACKS.append(cb)


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
            DELETE FROM table_meta;
            """
        )

    # Reset DuckDB tables
    if DUCKDB_PATH.exists():
        with get_duckdb_write_connection() as conn:
            try:
                tables = conn.execute("SHOW TABLES;").fetchall()
                for (t_name,) in tables:
                    conn.execute(f'DROP TABLE IF EXISTS "{t_name}";')
            except Exception:
                pass

    for cb in _ON_RESET_CALLBACKS:
        try:
            cb()
        except Exception:
            pass
