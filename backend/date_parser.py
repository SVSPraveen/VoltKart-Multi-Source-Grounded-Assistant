"""backend/date_parser.py - Tolerant multi-format document date parser.

Extracts dates from document content (primary) and filenames (fallback),
records the provenance source, detects date conflicts/disagreements,
and normalizes all valid dates to ISO 8601 (YYYY-MM-DD).
"""

from __future__ import annotations

import re
from datetime import datetime

from dateutil import parser as date_parser

from backend.models import DocumentDateResult

# Regex matching date indicator headers common in business documents
DATE_HEADER_PATTERN = re.compile(
    r"(?:document\s*date|effective\s*date|issue\s*date|issued\s*on|dated|last\s*updated|"
    r"revision\s*date|as\s*of)\s*[:\-–—]?\s*([^\n\r,\;\|\(\)]+)",
    re.IGNORECASE,
)

# Regex matching ISO dates in filenames or text (YYYY-MM-DD or YYYY_MM_DD)
# Uses negative lookahead/lookbehind for digits so underscores or hyphens in filenames don't break matching
ISO_FILENAME_PATTERN = re.compile(
    r"(?<!\d)(?P<year>20\d{2}|19\d{2})[-_](?P<month>0[1-9]|1[0-2])[-_](?P<day>0[1-9]|[12]\d|3[01])(?!\d)"
)

# Explicit day-month-year or month-day-year patterns with optional ordinal suffix
EXPLICIT_TEXT_DATE_PATTERN = re.compile(
    r"\b(?:(?P<day>\d{1,2})(?:st|nd|rd|th)?\s+(?P<month_name>january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\s+(?P<year>20\d{2}|19\d{2})|"
    r"(?P<month_name2>january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\s+(?P<day2>\d{1,2})(?:st|nd|rd|th)?,?\s+(?P<year2>20\d{2}|19\d{2})|"
    r"(?P<iso_year>20\d{2}|19\d{2})[-/.](?P<iso_month>0[1-9]|1[0-2])[-/.](?P<iso_day>0[1-9]|[12]\d|3[01]))\b",
    re.IGNORECASE,
)


def normalize_parsed_date(raw_date: str) -> str | None:
    """Normalize a raw date string to YYYY-MM-DD format."""
    clean_str = raw_date.strip().rstrip(".").strip()
    # Remove ordinal suffixes like 1st, 2nd, 3rd, 4th
    clean_str = re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", clean_str, flags=re.IGNORECASE)

    # Priority 1: Check ISO format (YYYY-MM-DD or YYYY/MM/DD) explicitly to prevent dayfirst confusion
    iso_match = re.match(r"^(\d{4})[-/.](0[1-9]|1[0-2])[-/.](0[1-9]|[12]\d|3[01])$", clean_str)
    if iso_match:
        y, mo, d = int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3))
        try:
            return datetime(y, mo, d).strftime("%Y-%m-%d")
        except ValueError:
            pass

    try:
        # Prefer dayfirst=True for international / Indian English dates (e.g. 1 April 2024)
        parsed = date_parser.parse(clean_str, dayfirst=True, fuzzy=True)
        if 1980 <= parsed.year <= 2050:
            return parsed.strftime("%Y-%m-%d")
    except Exception:
        pass

    return None


def extract_date_from_filename(filename: str) -> str | None:
    """Extract a YYYY-MM-DD date from a filename if present."""
    match = ISO_FILENAME_PATTERN.search(filename)
    if match:
        year, month, day = match.group("year"), match.group("month"), match.group("day")
        try:
            parsed = datetime(int(year), int(month), int(day))
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            return None
    return None


def extract_date_from_body(text: str) -> str | None:
    """Extract document date from text content."""
    # Check first ~2500 characters where document headers typically live
    header_chunk = text[:2500]

    # 1. Search for explicit date labels (e.g., "Document Date: 1 April 2024")
    for match in DATE_HEADER_PATTERN.finditer(header_chunk):
        candidate = match.group(1).strip()
        # Clean trailing text up to newline or parenthesis
        candidate = candidate.split("\n")[0].split("(")[0].strip()
        parsed = normalize_parsed_date(candidate)
        if parsed:
            return parsed

    # 2. Search for explicit full date expressions in header chunk
    match = EXPLICIT_TEXT_DATE_PATTERN.search(header_chunk)
    if match:
        parsed = normalize_parsed_date(match.group(0))
        if parsed:
            return parsed

    return None


def resolve_document_date(text: str, filename: str) -> DocumentDateResult:
    """Resolve document date adhering to R-017:

    - Body date is primary.
    - Filename date is fallback.
    - Disagreements between body and filename are flagged.
    - Undated documents rank last and are labeled as undated.
    """
    body_date = extract_date_from_body(text)
    filename_date = extract_date_from_filename(filename)

    if body_date and filename_date:
        disagreement = body_date != filename_date
        return DocumentDateResult(
            doc_date=body_date,
            source="body",
            date_disagreement=disagreement,
            body_date=body_date,
            filename_date=filename_date,
        )

    if body_date:
        return DocumentDateResult(
            doc_date=body_date,
            source="body",
            date_disagreement=False,
            body_date=body_date,
            filename_date=None,
        )

    if filename_date:
        return DocumentDateResult(
            doc_date=filename_date,
            source="filename",
            date_disagreement=False,
            body_date=None,
            filename_date=filename_date,
        )

    return DocumentDateResult(
        doc_date=None,
        source="undated",
        date_disagreement=False,
        body_date=None,
        filename_date=None,
    )
