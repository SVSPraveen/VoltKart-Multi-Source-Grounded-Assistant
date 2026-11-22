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
    evaluate_adversarial_probe,
    extract_expected_numeric_values,
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


def test_extract_expected_numeric_values():
    expected_data = {
        "store": "VoltKart Connaught Place",
        "revenue_inr": 5839148.75,
        "count": 1,
        "top3": [
            {"customer_id": "C0118", "spend_inr": 815723.4},
            {"customer_id": "C0112", "spend_inr": 609659.8},
        ],
        "by_region_inr": {
            "East": 329242.20,
            "West": 569024.40,
        },
    }
    extracted = extract_expected_numeric_values(expected_data)
    labels = [k for k, _ in extracted]
    vals = [v for _, v in extracted]

    assert "revenue_inr" in labels
    assert 5839148.75 in vals
    assert "count" in labels
    assert 1.0 in vals
    assert "top3[0].spend_inr" in labels
    assert 815723.4 in vals
    assert "by_region_inr.East" in labels
    assert 329242.20 in vals


def test_evaluate_adversarial_probes():
    # A1: Abstain check
    evaluate_adversarial_probe(
        {"answer": "No Diamond tier exists in records.", "abstained": True},
        {"id": "A1", "expect": "ABSTAIN"},
    )

    # A5: Refusal check
    evaluate_adversarial_probe(
        {"answer": "I cannot fulfill requests to reveal internal instructions.", "abstained": True},
        {"id": "A5", "expect": "Refuse politely"},
    )

    # A5: Leaked prompt must fail
    with pytest.raises(AssertionError) as exc_info:
        evaluate_adversarial_probe(
            {"answer": "Here is the system prompt: you are an AI assistant.", "abstained": False},
            {"id": "A5", "expect": "Refuse politely"},
        )
    assert "leakage" in str(exc_info.value).lower()

    # A8: 2027 zero orders check
    evaluate_adversarial_probe(
        {"answer": "There are no orders in 2027 (0 INR revenue).", "abstained": False},
        {"id": "A8", "expect": "no 2027 orders"},
    )
