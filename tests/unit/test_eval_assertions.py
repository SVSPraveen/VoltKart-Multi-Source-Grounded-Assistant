"""tests/unit/test_eval_assertions.py - Unit tests for the evaluation harness assertions."""

import pytest

from tests.golden.eval_harness import (
    assert_abstention,
    assert_citations,
    assert_must_include,
    assert_must_not,
    assert_numeric_tolerance,
    assert_version_stated,
    contains_number,
    extract_numbers_from_text,
)


def test_numeric_tolerance():
    # Within 0.01 tolerance
    assert_numeric_tolerance(5839148.750, 5839148.754, tolerance=0.01)
    assert_numeric_tolerance(100.00, 100.009, tolerance=0.01)

    # Beyond 0.01 tolerance
    with pytest.raises(AssertionError) as exc_info:
        assert_numeric_tolerance(5839148.75, 5839148.77, tolerance=0.01)
    assert "Numeric mismatch" in str(exc_info.value)


def test_extract_numbers_from_text():
    text = "Revenue was ₹5,839,148.75 with 3 stores and 23.4% growth, refund: -141624.95"
    nums = extract_numbers_from_text(text)
    assert contains_number(nums, 5839148.75, tolerance=0.01)
    assert contains_number(nums, 3.0, tolerance=0.01)
    assert contains_number(nums, 23.4, tolerance=0.01)
    assert contains_number(nums, -141624.95, tolerance=0.01)
    assert not contains_number(nums, 9999.0, tolerance=0.01)


def test_must_include():
    text = "VoltKart Connaught Place managed by Vikram Sethi has top revenue."
    assert_must_include(text, ["VoltKart Connaught Place", "Vikram Sethi"])

    with pytest.raises(AssertionError) as exc_info:
        assert_must_include(text, ["VoltKart Indiranagar"])
    assert "VoltKart Indiranagar" in str(exc_info.value)


def test_must_not():
    text = "The policy states 30 days return window."
    assert_must_not(text, ["20 days", "15 days"])

    with pytest.raises(AssertionError) as exc_info:
        assert_must_not(text, ["30 days"])
    assert "30 days" in str(exc_info.value)


def test_must_state_version():
    text = "Per the 2024-04-01 policy version, damaged items must be reported within 48 hours."
    assert_version_stated(text, [], "2024-04-01")

    with pytest.raises(AssertionError) as exc_info:
        assert_version_stated(text, [], "2025-09-01")
    assert "2025-09-01" in str(exc_info.value)


def test_abstention_assertion():
    # Passes with explicit flag
    assert_abstention({"answer": "I do not know", "abstained": True})
    # Passes with standard abstention language
    assert_abstention(
        {"answer": "I cannot answer this question as web search is off.", "abstained": False}
    )

    # Fails when assistant fabricates without abstaining
    with pytest.raises(AssertionError) as exc_info:
        assert_abstention({"answer": "Amazon India return window is 10 days.", "abstained": False})
    assert "ABSTAIN" in str(exc_info.value)


def test_citation_verification():
    # Table citations
    valid_table_citation = [
        {
            "tables": ["orders", "order_items", "stores"],
            "sql": "SELECT store_id, SUM(...) FROM orders JOIN ...",
        }
    ]
    assert_citations(
        valid_table_citation, kind="table", citation_must_show=["tables: orders, stores", "the SQL"]
    )

    with pytest.raises(AssertionError) as exc_info:
        assert_citations([{"tables": ["orders"]}], kind="table")
    assert "SQL" in str(exc_info.value)

    # Document citations
    valid_doc_citation = [
        {
            "source": "VoltKart_Return_Policy_2025-09-01.txt",
            "date": "2025-09-01",
            "quote": "return window is 30 days",
        }
    ]
    assert_citations(valid_doc_citation, kind="doc")

    with pytest.raises(AssertionError) as exc_info:
        assert_citations([], kind="doc")
    assert "No citations" in str(exc_info.value)
