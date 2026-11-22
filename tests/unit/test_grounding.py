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


def test_grounding_date_hyphens_not_negative():
    rows = [{"date_col": "2025-01-15", "val": 100}]
    question = "Show orders for 2025-01-15"
    prose = "Orders for 2025-01-15 showed 100 units."
    res = verify_numeric_grounding(prose, query_rows=rows, question_text=question)
    assert res.grounded
    assert len(res.ungrounded_numbers) == 0


def test_grounding_allows_sql_query_parameters():
    rows = [{"revenue": 5000.0}]
    sql = "SELECT SUM(amount) AS revenue FROM orders WHERE order_date >= '2025-01-01' LIMIT 5;"
    question = "What was the revenue?"
    prose = "From 2025-01-01 the revenue was ₹5,000.00 across 5 items."
    res = verify_numeric_grounding(prose, query_rows=rows, question_text=question, sql_query=sql)
    assert res.grounded
