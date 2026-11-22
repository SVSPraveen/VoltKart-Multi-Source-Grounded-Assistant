"""tests/unit/test_security_audit.py - Security Audit Verification Suite.

Threat model: Internet-reachable FastAPI app that executes LLM-written SQL on user-uploaded files.
Verifies:
1. AST validation strictly enforces single-SELECT and blocks all external/introspection functions.
2. DuckDB read-only connection + enable_external_access=false locks engine.
3. Cross-platform path traversal neutralization in filenames and API parameters.
4. Input validation on chat_id and sha256 preventing header injection and path traversal.
"""

from __future__ import annotations

import duckdb
import pytest
from fastapi import HTTPException

from backend.api import validate_chat_id, validate_sha256
from backend.ingestion import sanitize_filename
from backend.sql_guard import validate_sql
from backend.storage import get_duckdb_read_connection


def test_sql_guard_blocks_ddl_and_dml():
    """Ensure all write and schema modification statements are rejected."""
    malicious_queries = [
        "DROP TABLE orders;",
        "TRUNCATE orders;",
        "DELETE FROM customers WHERE 1=1;",
        "UPDATE products SET list_price_inr = 0;",
        "INSERT INTO stores (store_id) VALUES ('S99');",
        "ALTER TABLE orders ADD COLUMN hack TEXT;",
        "CREATE TABLE backdoors (id INT);",
    ]
    for q in malicious_queries:
        res = validate_sql(q, allowed_tables=["orders", "customers", "products", "stores"])
        assert not res.is_valid
        assert (
            "unauthorized operation" in res.error_message.lower()
            or "only select" in res.error_message.lower()
        )


def test_sql_guard_blocks_introspection_and_external_functions():
    """Ensure internal DuckDB/SQLite/Postgres introspection and external readers are blocked."""
    introspection_queries = [
        "SELECT * FROM read_csv('/etc/passwd');",
        "SELECT * FROM read_parquet('s3://bucket/key');",
        "SELECT * FROM duckdb_settings();",
        "SELECT * FROM duckdb_secrets();",
        "SELECT * FROM duckdb_memory();",
        "SELECT * FROM sqlite_master;",
        "SELECT * FROM pg_catalog.pg_tables;",
        "SELECT current_setting('access_mode');",
        "SELECT getenv('SECRET_KEY');",
    ]
    for q in introspection_queries:
        res = validate_sql(q, allowed_tables=["orders", "customers"])
        assert not res.is_valid
        assert (
            "unauthorized" in res.error_message.lower()
            or "does not exist" in res.error_message.lower()
            or "blocked" in res.error_message.lower()
        )


def test_sql_guard_blocks_multi_statement_injection():
    """Ensure semicolons cannot chain secondary statements."""
    chained = "SELECT 1; DROP TABLE orders;"
    res = validate_sql(chained, allowed_tables=["orders"])
    assert not res.is_valid
    assert "multiple sql statements detected" in res.error_message.lower()


def test_duckdb_engine_level_external_access_disabled():
    """Even if an attacker bypassed AST, DuckDB configuration must block file access."""
    with get_duckdb_read_connection() as conn:
        with pytest.raises(duckdb.Error) as exc_info:
            conn.execute("SELECT * FROM read_csv_auto('nonexistent.csv');")
        err_str = str(exc_info.value).lower()
        assert (
            "disabled by configuration" in err_str
            or "enable_external_access" in err_str
            or "not allowed" in err_str
        )


def test_sanitize_filename_cross_platform():
    """Path traversal sequences across POSIX and Windows must be neutralized."""
    cases = [
        ("../../etc/shadow", "shadow"),
        ("..\\..\\windows\\system32\\cmd.exe", "cmd.exe"),
        ("/root/secret.csv", "secret.csv"),
        ("file\x00name.csv", "filename.csv"),
        ('test"name<file>|run?.csv', "testnamefilerun.csv"),
    ]
    for raw, expected in cases:
        clean = sanitize_filename(raw)
        assert "/" not in clean
        assert "\\" not in clean
        assert "\x00" not in clean
        assert clean == expected


def test_api_chat_id_validation():
    """Invalid chat_id containing header injection or traversal must raise HTTP 400."""
    valid_ids = ["chat_12345", "chat-abc_xyz", "chat_default", "session.1"]
    for cid in valid_ids:
        assert validate_chat_id(cid) == cid

    invalid_ids = [
        "../../etc/passwd",
        "chat\r\nSet-Cookie: session=hacked",
        "chat<script>alert(1)</script>",
        "chat id with spaces",
        "",
        "a" * 65,  # Too long
    ]
    for bad_id in invalid_ids:
        with pytest.raises(HTTPException) as exc_info:
            validate_chat_id(bad_id)
        assert exc_info.value.status_code == 400


def test_api_sha256_validation():
    """Invalid sha256 hash format must raise HTTP 400."""
    valid_hash = "a" * 64
    assert validate_sha256(valid_hash) == valid_hash

    invalid_hashes = [
        "not_a_hash",
        "a" * 63,  # Too short
        "a" * 65,  # Too long
        "../../etc/passwd",
        "g" * 64,  # Non-hex character
    ]
    for bad_hash in invalid_hashes:
        with pytest.raises(HTTPException) as exc_info:
            validate_sha256(bad_hash)
        assert exc_info.value.status_code == 400
