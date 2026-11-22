"""tests/unit/test_ingestion_robustness.py - Robustness tests for upload edge cases (REVIEW R-023).

Verifies graceful handling and clean user-facing error reporting for:
- Idempotent uploads (same file twice by SHA-256)
- Empty files (0 bytes)
- Oversize files (> 50MB)
- Legacy .doc files (suggesting .docx)
- Directory traversal in filenames
- Semicolon delimiters and UTF-8 BOM
- Corrupted file headers
- Zero raw stack traces leaked to users
"""

import pytest

from backend.ingestion import (
    ingest_files,
    process_single_file,
    sanitize_filename,
    validate_file_content,
)
from backend.storage import reset_storage


def setup_function():
    """Reset database state before each test."""
    reset_storage()


def test_idempotent_uploads_sha256():
    """Uploading the same file twice must be idempotent (R-023)."""
    content = b"Document Date: 2025-05-01\n# Overview\nSample company guidance.\n"
    filename = "guidance.txt"

    # First upload
    t1, meta1 = process_single_file(filename, content)
    # Second upload of identical content
    t2, meta2 = process_single_file(filename, content)

    assert meta1.sha256 == meta2.sha256
    summary = ingest_files([(filename, content), (filename, content)])
    # Only one document record should exist in the summary
    doc_records = [d for d in summary.documents if d.file_name == filename]
    assert len(doc_records) == 1


def test_reject_empty_file():
    """Empty files (0 bytes) must be rejected with a clean message (R-023)."""
    with pytest.raises(ValueError, match="is empty"):
        validate_file_content("empty.csv", b"")

    summary = ingest_files([("empty.csv", b"")])
    assert len(summary.errors) == 1
    assert "empty" in summary.errors[0].error.lower()


def test_reject_oversize_file():
    """Files exceeding size limit (> 50MB) must be rejected cleanly (R-023)."""
    fake_huge = b"x" * (51 * 1024 * 1024)
    with pytest.raises(ValueError, match="exceeds maximum allowed size"):
        validate_file_content("huge.csv", fake_huge)


def test_reject_legacy_doc_format():
    """Legacy .doc binary format must be rejected with conversion instruction (R-023)."""
    # OLE Compound File header magic
    ole_header = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 100
    with pytest.raises(ValueError, match="legacy .doc format"):
        validate_file_content("old_spec.doc", ole_header)

    summary = ingest_files([("legacy_file.doc", ole_header)])
    assert len(summary.errors) == 1
    assert "convert to .docx" in summary.errors[0].error.lower()


def test_sanitize_path_traversal_filename():
    """Directory traversal sequences in uploaded filenames must be stripped (R-023)."""
    malicious_names = [
        "../../etc/passwd.csv",
        "..\\..\\windows\\system32\\calc.exe.csv",
        "nested/dir/table.csv",
    ]
    for raw in malicious_names:
        clean = sanitize_filename(raw)
        assert "/" not in clean
        assert "\\" not in clean
        assert clean.endswith(".csv")


def test_semicolon_delimited_csv_ingestion():
    """CSV files using semicolon delimiters must load correctly into DuckDB (R-023)."""
    semicolon_csv = b"item_id;category;amount\nA1;Hardware;150\nA2;Software;250\n"
    summary = ingest_files([("items_semi.csv", semicolon_csv)])
    assert len(summary.errors) == 0
    loaded_tbl = next(t for t in summary.tables if t.table_name == "items_semi")
    assert loaded_tbl.row_count == 2
    assert loaded_tbl.column_count == 3


def test_utf8_bom_csv_ingestion():
    """CSV files with UTF-8 BOM must load without corrupting the first column name (R-023)."""
    bom_csv = b"\xef\xbb\xbfcust_id,score\nC01,95\nC02,88\n"
    summary = ingest_files([("customers_bom.csv", bom_csv)])
    assert len(summary.errors) == 0
    loaded_tbl = next(t for t in summary.tables if t.table_name == "customers_bom")
    # First column name must not contain BOM character
    col_names = [c.name for c in loaded_tbl.columns]
    assert "cust_id" in col_names
    assert "\ufeffcust_id" not in col_names


def test_no_raw_stack_traces_in_error_summary():
    """Error responses must provide clean messages, never raw Python stack traces (R-023)."""
    invalid_files = [
        ("corrupt.pdf", b"Not a valid PDF at all"),
        ("empty.txt", b""),
        ("unsupported.exe", b"MZ\x90\x00\x03"),
    ]
    summary = ingest_files(invalid_files)
    assert len(summary.errors) == 3
    for err in summary.errors:
        assert "Traceback" not in err.error
        assert 'File "' not in err.error
        assert len(err.error) > 0
