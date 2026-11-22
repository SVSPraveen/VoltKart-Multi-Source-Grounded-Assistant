"""tests/unit/test_web_search.py - Server-Gated Web Search & Outbound Auditing Tests (B8, R-011).

Verifies:
1. Server-side tool gating (R-011): When web toggle is OFF, ZERO outbound network search calls are made.
2. Q17 honest abstention when web search is disabled.
3. Q18a live factual retrieval when web toggle is ON, citing title + URL + retrieved_at.
4. Q18b multi-source cross-modal comparison combining web fact and document fact with structured provenance.
5. Factual grounding: Factual numbers come from web/docs, never hallucinated from model memory.
"""

from __future__ import annotations

import pytest

from backend.assistant import ask_assistant
from backend.storage import init_sqlite_db, reset_storage
from backend.web_search import (
    get_outbound_search_count,
    reset_outbound_search_count,
    run_web_qa,
)


@pytest.fixture(autouse=True)
def setup_storage():
    """Ensure clean database and reset outbound search counter for every test."""
    reset_storage()
    init_sqlite_db()
    reset_outbound_search_count()


def test_q17_web_off_assert_zero_outbound_calls():
    """Server-side tool gating test (R-011): Assert ZERO outbound search calls when web is OFF."""
    reset_outbound_search_count()

    response = ask_assistant(
        "What is Amazon India's return window for smartphones?",
        chat_id="chat_test_web_off",
        web_enabled=False,
    )

    # 1. Assert ZERO outbound search calls were made to any search provider
    assert get_outbound_search_count() == 0, (
        f"Server-side gating violated: {get_outbound_search_count()} outbound calls made when web was OFF."
    )

    # 2. Assert assistant honestly abstains
    assert response["abstained"] is True
    assert (
        "web search is disabled" in response["answer"].lower()
        or "cannot answer" in response["answer"].lower()
    )
    assert len(response["citations"]) == 0


def test_q18a_web_on_factual_retrieval_and_citation():
    """Live web search when web toggle is ON: verifies outbound call, factual answer, and citation."""
    reset_outbound_search_count()

    response = ask_assistant(
        "What is Amazon India's return window for smartphones?",
        chat_id="chat_test_web_on",
        web_enabled=True,
    )

    # 1. Assert outbound search call was made
    assert get_outbound_search_count() > 0, "Expected outbound search call when web toggle is ON."

    # 2. Assert answer is not empty and not abstained
    assert response["abstained"] is False
    assert "amazon" in response["answer"].lower()
    assert "7" in response["answer"] or "day" in response["answer"].lower()

    # 3. Assert structured web citation contains required metadata fields
    citations = response.get("citations", [])
    assert len(citations) >= 1
    web_cit = citations[0]
    assert web_cit.get("type") == "web"
    assert "title" in web_cit and bool(web_cit["title"])
    assert "url" in web_cit and web_cit["url"].startswith("http")
    assert "retrieved_at" in web_cit and "Z" in web_cit["retrieved_at"]


def test_q18b_multi_source_comparison_web_and_document():
    """Multi-source comparison (Q18b): Combines web fact from Turn 18a and document policy fact."""
    chat_id = "chat_test_web_comparison"

    # Turn 18a: Amazon India return window
    res_18a = ask_assistant(
        "What is Amazon India's return window for smartphones?",
        chat_id=chat_id,
        web_enabled=True,
    )
    assert res_18a["abstained"] is False

    # Turn 18b: Comparison with VoltKart's smartphone return window
    res_18b = ask_assistant(
        "How does that compare with VoltKart's smartphone return window?",
        chat_id=chat_id,
        web_enabled=True,
    )

    ans = res_18b["answer"].lower()
    # Must include the 7-day policy window
    assert "7" in ans

    # Must mention both Amazon and VoltKart
    assert "amazon" in ans
    assert "voltkart" in ans

    # Must contain both web citation and document citation
    citations = res_18b.get("citations", [])
    has_web_cit = any(c.get("type") == "web" for c in citations)
    has_doc_cit = any(
        c.get("type") == "document" and "Return_Policy" in str(c.get("source", ""))
        for c in citations
    )
    assert has_web_cit, "Comparison answer missing web citation."
    assert has_doc_cit, "Comparison answer missing VoltKart return policy document citation."


def test_server_gate_direct_call_blocks_when_off():
    """Direct call to run_web_qa with web_enabled=False must never call network."""
    reset_outbound_search_count()
    qa_res = run_web_qa("Amazon return policy", web_enabled=False)
    assert get_outbound_search_count() == 0
    assert qa_res.abstained is True
    assert "disabled" in qa_res.answer.lower()


def test_general_web_search_does_not_hallucinate_amazon_return_policy():
    """Non-Amazon queries must not fabricate or default to Amazon return policy answers."""
    reset_outbound_search_count()
    qa_res = run_web_qa(
        "What is the official repair service for Apple iPhones in India?",
        web_enabled=True,
    )
    assert get_outbound_search_count() > 0
    # Must not default to Amazon India official policy
    assert "amazon india's official return policy" not in qa_res.answer.lower()
    if not qa_res.abstained:
        assert len(qa_res.citations) >= 1
        assert qa_res.citations[0]["type"] == "web"
