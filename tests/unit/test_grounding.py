"""tests/unit/test_grounding.py - Unit tests for deterministic numeric grounding check (R-003)."""

from __future__ import annotations

from backend.grounding import verify_numeric_grounding


def test_grounding_passes_when_all_numbers_in_rows():
    rows = [{"store_name": "Store Alpha", "revenue": 5839148.75, "rank": 1}]
    question = "Which store had highest revenue in 2025?"
    prose = "In 2025, Store Alpha had the highest revenue of ₹58,39,148.75 and ranked 1."
    res = verify_numeric_grounding(prose, query_rows=rows, question_text=question)
    assert res.grounded
    assert len(res.ungrounded_numbers) == 0


def test_grounding_fails_on_hallucinated_number():
    rows = [{"store_name": "Store Alpha", "revenue": 5839148.75}]
    question = "Which store had highest revenue in 2025?"
    prose = "In 2025, Store Alpha made ₹58,39,148.75 with an extra 999 bonus points."
    res = verify_numeric_grounding(prose, query_rows=rows, question_text=question)
    assert not res.grounded
    assert 999.0 in res.ungrounded_numbers


def test_grounding_allows_quarter_numbers():
    rows = [{"customer_name": "User X", "count": 1}]
    question = "How many customers bought in Q1 2026?"
    prose = "In Q1 2026, 1 customer bought items."
    res = verify_numeric_grounding(prose, query_rows=rows, question_text=question)
    assert res.grounded


def test_grounding_empty_prose():
    res = verify_numeric_grounding("No matching records were found.", query_rows=[])
    assert res.grounded
