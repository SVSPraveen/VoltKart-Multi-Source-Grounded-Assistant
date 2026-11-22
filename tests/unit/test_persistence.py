"""tests/unit/test_persistence.py - Process restart persistence test (spec section 2 & 7.1).

Verifies that ingested DuckDB relational tables and SQLite document metadata/FTS5 indexes
persist on disk and remain fully queryable across application restarts and new connections.
"""

import subprocess
import sys

from backend.ingestion import ingest_files
from backend.storage import (
    DUCKDB_PATH,
    SQLITE_DB_PATH,
    reset_storage,
)


def test_persistence_across_process_restart():
    """Prove DuckDB tables and SQLite metadata survive process termination and restart."""
    # Step 1: Clean slate
    reset_storage()

    # Step 2: Ingest a table and a document
    csv_content = b"metric_id,score\nM01,92.5\nM02,88.0\nM03,95.1\n"
    doc_content = (
        b"OPERATIONS MANUAL\n"
        b"=================\n"
        b"Document Date: 2025-08-10\n\n"
        b"1. Safety Protocols\n"
        b"Always verify that safety latches are secured before operating machinery.\n"
    )

    summary = ingest_files(
        [
            ("metrics.csv", csv_content),
            ("operations_manual.txt", doc_content),
        ]
    )
    assert len(summary.errors) == 0

    # Ensure files exist on disk
    assert DUCKDB_PATH.exists(), "DuckDB file was not created on disk"
    assert SQLITE_DB_PATH.exists(), "SQLite file was not created on disk"

    # Step 3: Spawn an independent python subprocess to simulate complete process termination and restart
    check_script = """
import sys
import duckdb
import sqlite3
from pathlib import Path

duckdb_path = sys.argv[1]
sqlite_path = sys.argv[2]

# Verify DuckDB table and rows in new connection
ddb = duckdb.connect(duckdb_path, read_only=True)
count = ddb.execute("SELECT COUNT(*) FROM metrics").fetchone()[0]
assert count == 3, f"Expected 3 rows in metrics, got {count}"
ddb.close()

# Verify SQLite files and FTS5 search in new connection
sdb = sqlite3.connect(sqlite_path)
file_row = sdb.execute("SELECT file_name, doc_date FROM files WHERE file_name = 'operations_manual.txt'").fetchone()
assert file_row is not None, "File record missing in SQLite"
assert file_row[1] == "2025-08-10", f"Unexpected doc_date {file_row[1]}"

# Verify FTS5 query
fts_match = sdb.execute("SELECT chunk_id FROM chunks_fts WHERE chunks_fts MATCH 'machinery'").fetchone()
assert fts_match is not None, "FTS5 query failed to match indexed term"
sdb.close()

print("PERSISTENCE_VERIFIED")
"""

    res = subprocess.run(
        [sys.executable, "-c", check_script, str(DUCKDB_PATH), str(SQLITE_DB_PATH)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert res.returncode == 0, f"Process restart check failed: {res.stderr}"
    assert "PERSISTENCE_VERIFIED" in res.stdout
