"""tests/unit/test_date_parser.py - Unit tests for date parser (R-017).

Verifies multi-format parsing across all sample bundle date formats,
filename fallback, body date priority, disagreement detection, and ordinals.
"""

from backend.date_parser import (
    extract_date_from_body,
    extract_date_from_filename,
    normalize_parsed_date,
    resolve_document_date,
)


def test_bundle_date_formats():
    """Verify every date format present in the sample bundle."""
    bundle_dates = {
        "10 March 2025": "2025-03-10",
        "20 October 2025": "2025-10-20",
        "1 April 2024": "2024-04-01",
        "15 January 2025": "2025-01-15",
        "2025-09-01": "2025-09-01",
        "5 November 2025": "2025-11-05",
        "1 July 2024": "2024-07-01",
        "1 February 2026": "2026-02-01",
    }
    for raw, expected in bundle_dates.items():
        assert normalize_parsed_date(raw) == expected, f"Failed for {raw}"


def test_ordinal_and_variant_dates():
    """Verify ordinal suffixes and alternative month-first formats."""
    variants = {
        "1st April 2024": "2024-04-01",
        "2nd March 2025": "2025-03-02",
        "3rd May 2025": "2025-05-03",
        "20th October 2025": "2025-10-20",
        "October 20, 2025": "2025-10-20",
        "January 15, 2025": "2025-01-15",
        "2025/11/05": "2025-11-05",
    }
    for raw, expected in variants.items():
        assert normalize_parsed_date(raw) == expected, f"Failed for {raw}"


def test_extract_date_from_filename():
    """Verify extraction from standard filenames."""
    assert extract_date_from_filename("Policy_2025-01-15.docx") == "2025-01-15"
    assert extract_date_from_filename("Notice_2024_04_01.pdf") == "2024-04-01"
    assert extract_date_from_filename("undated_document.pdf") is None


def test_extract_date_from_body_indicators():
    """Verify date header indicator matching in document body text."""
    body1 = "Document Date: 15 January 2025\nVersion 2.0"
    assert extract_date_from_body(body1) == "2025-01-15"

    body2 = "Effective Date: 1 July 2024\nVersion 2024.1"
    assert extract_date_from_body(body2) == "2024-07-01"

    body3 = "Issued on: 5 November 2025\nGeneral Notice"
    assert extract_date_from_body(body3) == "2025-11-05"


def test_resolve_document_date_body_primary():
    """Body date must be primary over filename date (R-017)."""
    text = "Document Date: 10 March 2025\nContent"
    filename = "Document_2025-03-10.docx"
    res = resolve_document_date(text, filename)

    assert res.doc_date == "2025-03-10"
    assert res.source == "body"
    assert res.date_disagreement is False


def test_resolve_document_date_disagreement_flagged():
    """Disagreement between body and filename date must be flagged (R-017)."""
    text = "Document Date: 15 January 2025\nContent"
    filename = "Document_2024-04-01.docx"  # Conflicting filename
    res = resolve_document_date(text, filename)

    assert res.doc_date == "2025-01-15"  # Body date takes precedence
    assert res.source == "body"
    assert res.date_disagreement is True
    assert res.filename_date == "2024-04-01"


def test_resolve_document_date_filename_fallback():
    """Filename date is used when body lacks date (R-017)."""
    text = "Undated internal guidance memo without any date header."
    filename = "Guidance_2025-06-12.pdf"
    res = resolve_document_date(text, filename)

    assert res.doc_date == "2025-06-12"
    assert res.source == "filename"
    assert res.date_disagreement is False


def test_resolve_document_date_undated():
    """Completely undated documents rank last and are labeled undated (R-017)."""
    text = "General handbook with no temporal markers."
    filename = "general_handbook.txt"
    res = resolve_document_date(text, filename)

    assert res.doc_date is None
    assert res.source == "undated"
    assert res.date_disagreement is False
