"""backend/grounding.py - Deterministic numeric grounding verifier (R-003).

Enforces:
1. Every integer or float appearing in generated assistant prose MUST exist in:
   - The executed SQL query result rows (cell values, aggregates, counts).
   - The user question prompt (e.g. '2025', 'top 3', 'Q1').
   - The query result row count or enumeration ranks (1..N).
2. Prevents model hallucinations, invented arithmetic, and untracked counts.
"""

from __future__ import annotations

import re
from typing import Any


class GroundingResult:
    """Result of numeric grounding verification."""

    def __init__(
        self,
        grounded: bool,
        ungrounded_numbers: list[float] | None = None,
        allowed_pool: list[float] | None = None,
        extracted_prose_numbers: list[float] | None = None,
        details: str = "",
    ) -> None:
        self.grounded = grounded
        self.ungrounded_numbers = ungrounded_numbers or []
        self.allowed_pool = allowed_pool or []
        self.extracted_prose_numbers = extracted_prose_numbers or []
        self.details = details

    def __repr__(self) -> str:
        return f"GroundingResult(grounded={self.grounded}, ungrounded={self.ungrounded_numbers})"


def extract_numbers(text: str) -> list[float]:
    """Extract numeric values from text, stripping currencies, commas, and percentage signs."""
    # Replace currency symbols, commas, and percentage signs
    cleaned = re.sub(r"[₹$,%]", "", text)
    # Match floats and integers; avoid interpreting date hyphens as negative signs
    tokens = re.findall(r"(?<![\w\d])[-+]?\d+(?:\.\d+)?|\b\d+(?:\.\d+)?", cleaned)
    numbers: list[float] = []
    for tok in tokens:
        try:
            val = float(tok)
            numbers.append(val)
        except ValueError:
            continue
    return numbers


def build_allowed_number_pool(
    query_rows: list[dict[str, Any]] | None,
    question_text: str = "",
    row_count: int | None = None,
    extra_allowed: list[float] | None = None,
    sql_query: str = "",
) -> list[float]:
    """Collect all valid, grounded numbers from SQL results, query text, derived sums, and prompt."""
    allowed: list[float] = [0.0]  # Zero is always a valid count or empty sum

    # 1. Numbers from query rows
    if query_rows:
        for row in query_rows:
            for v in row.values():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    allowed.append(float(v))
                elif isinstance(v, str):
                    for num in extract_numbers(v):
                        allowed.append(num)

    # 2. Numbers from user question prompt
    if question_text:
        for num in extract_numbers(question_text):
            allowed.append(num)
        # Check for quarter mentions (e.g. Q1 -> 1)
        quarter_match = re.search(r"\bQ([1-4])\b", question_text, re.IGNORECASE)
        if quarter_match:
            allowed.append(float(quarter_match.group(1)))

    # 3. Numbers from executed SQL query (e.g. explicit dates or limits)
    if sql_query:
        for num in extract_numbers(sql_query):
            allowed.append(num)

    # 4. Row count and enumeration ranks (1..N)
    effective_count = row_count if row_count is not None else (len(query_rows) if query_rows else 0)
    allowed.append(float(effective_count))
    for r in range(1, effective_count + 1):
        allowed.append(float(r))

    # 5. Extra derived values computed in code (e.g. grand total sums, reconciliation totals)
    if extra_allowed:
        for val in extra_allowed:
            if val is not None:
                allowed.append(float(val))

    return allowed


def verify_numeric_grounding(
    prose_text: str,
    query_rows: list[dict[str, Any]] | None,
    question_text: str = "",
    row_count: int | None = None,
    extra_allowed: list[float] | None = None,
    sql_query: str = "",
    tolerance: float = 0.01,
) -> GroundingResult:
    """Verify that every number in prose is grounded in query results or question prompt.

    Args:
        prose_text: The generated assistant answer string.
        query_rows: The executed SQL result row dictionaries.
        question_text: The user input question string.
        row_count: Optional explicit row count.
        extra_allowed: Optional list of code-derived numbers (e.g. sum of rows).
        sql_query: Optional executed SQL query string.
        tolerance: Numeric comparison tolerance (default: 0.01).

    Returns:
        GroundingResult with verification status and any ungrounded numbers.
    """
    prose_numbers = extract_numbers(prose_text)
    if not prose_numbers:
        return GroundingResult(grounded=True, details="No numbers present in prose.")

    allowed_pool = build_allowed_number_pool(
        query_rows=query_rows,
        question_text=question_text,
        row_count=row_count,
        extra_allowed=extra_allowed,
        sql_query=sql_query,
    )

    ungrounded: list[float] = []
    for num in prose_numbers:
        # Check if num matches any number in allowed_pool within tolerance
        matched = any(abs(num - a) <= tolerance for a in allowed_pool)
        if not matched:
            ungrounded.append(num)

    if ungrounded:
        return GroundingResult(
            grounded=False,
            ungrounded_numbers=ungrounded,
            allowed_pool=allowed_pool,
            extracted_prose_numbers=prose_numbers,
            details=f"Detected ungrounded numbers in prose: {ungrounded}",
        )

    return GroundingResult(
        grounded=True,
        allowed_pool=allowed_pool,
        extracted_prose_numbers=prose_numbers,
        details="All prose numbers verified and grounded.",
    )
