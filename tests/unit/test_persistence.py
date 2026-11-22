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
from pathlib import Path

# Add project root to sys.path
root = Path.cwd()
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

import duckdb
import sqlite3
from backend.ingestion import get_current_ingestion_summary, get_active_schema_card

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

fts_match = sdb.execute("SELECT chunk_id FROM chunks_fts WHERE chunks_fts MATCH 'machinery'").fetchone()
assert fts_match is not None, "FTS5 query failed to match indexed term"
sdb.close()

# Verify backend ingestion summary and schema card in completely fresh process
summary = get_current_ingestion_summary()
assert len(summary.tables) == 1, f"Expected 1 table in summary after restart, got {len(summary.tables)}"
assert summary.tables[0].table_name == "metrics"
assert summary.tables[0].row_count == 3
assert summary.tables[0].primary_key == "metric_id"
assert len(summary.documents) == 1
assert summary.documents[0].doc_date == "2025-08-10"

card = get_active_schema_card()
assert "# Database Schema Card" in card
assert "Table: `metrics`" in card
assert "`metric_id`" in card

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


def test_chat_and_followup_persistence_across_process_restart():
    """Verify chat sessions, messages, and follow-up contextualization survive process termination (spec 7.5, C6)."""
    from backend.assistant import ask_assistant

    reset_storage()
    chat_id = "test_restart_chat_followup"

    # Step 1: Turn 1 in current process
    t1_res = ask_assistant(
        "Which store had the highest revenue in 2025, and who manages it?",
        chat_id=chat_id,
    )
    assert "Vikram Sethi" in t1_res["answer"]
    assert "S04" in str(t1_res.get("metadata", {}))

    # Step 2: Spawn independent Python subprocess to simulate process termination and reboot
    followup_script = """
import sys
from pathlib import Path
root = Path.cwd()
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

import sqlite3
from backend.assistant import ask_assistant
from backend.storage import SQLITE_DB_PATH

chat_id = sys.argv[1]

# 1. Verify SQLite chat row and message history exist in fresh process
conn = sqlite3.connect(str(SQLITE_DB_PATH))
chat_row = conn.execute("SELECT chat_id FROM chats WHERE chat_id = ?", (chat_id,)).fetchone()
assert chat_row is not None, f"Chat session {chat_id} not found in SQLite"

msg_rows = conn.execute("SELECT role, content, status FROM messages WHERE chat_id = ? ORDER BY created_at", (chat_id,)).fetchall()
assert len(msg_rows) >= 2, f"Expected >= 2 messages, found {len(msg_rows)}"
assert msg_rows[0][0] == "user"
assert msg_rows[1][0] == "assistant"
assert msg_rows[1][2] == "completed"
conn.close()

# 2. Execute follow-up turn in fresh process requiring contextualization from disk
t2_res = ask_assistant(
    "Who were the top 3 customers by spend at that store in 2025?",
    chat_id=chat_id,
)
assert t2_res.get("interpreted_as") is not None, "Interpreted_as metadata missing in follow-up turn"
assert "S04" in t2_res["interpreted_as"], f"Expected S04 in interpreted_as, got {t2_res['interpreted_as']}"
assert "Aarav Kulkarni" in t2_res["answer"], f"Expected Aarav Kulkarni in answer: {t2_res['answer']}"

# 3. Execute conversational summary turn (Q20 core requirement) in fresh process
t3_res = ask_assistant(
    "Summarize what we discussed so far.",
    chat_id=chat_id,
)
assert "Summary" in t3_res["answer"]
assert "Vikram Sethi" in t3_res["answer"] or "highest revenue" in t3_res["answer"].lower()

print("CHAT_FOLLOWUP_PERSISTENCE_VERIFIED")
"""

    res = subprocess.run(
        [sys.executable, "-c", followup_script, chat_id],
        capture_output=True,
        text=True,
        check=False,
    )

    assert res.returncode == 0, f"Followup restart check failed: {res.stderr}\nOutput: {res.stdout}"
    assert "CHAT_FOLLOWUP_PERSISTENCE_VERIFIED" in res.stdout
