"""tests/unit/test_chat_isolation.py - Multi-Chat Isolation and Zero-Leakage Tests (B9, R-012).

Verifies:
1. Planted marker phrase in Chat A is completely invisible to Chat B.
2. Contextual follow-up entity resolution (e.g. "that store") does not leak across chats.
3. Chat summary ("Summarize what we discussed so far") in Chat B contains zero knowledge of Chat A topics.
4. Independent chat lifecycle (creation, message retrieval, deletion) does not affect other chats.
"""

from __future__ import annotations

import uuid

import pytest

from backend.assistant import ask_assistant
from backend.storage import (
    create_chat,
    delete_chat,
    get_chat_messages,
    init_sqlite_db,
    reset_storage,
)


@pytest.fixture(autouse=True)
def setup_storage():
    """Ensure clean database for isolation tests."""
    reset_storage()
    init_sqlite_db()


def test_planted_marker_isolation_across_chats():
    """Plant a secret marker phrase in Chat A; assert Chat B has zero knowledge of it."""
    chat_a = f"chat_A_{uuid.uuid4().hex[:6]}"
    chat_b = f"chat_B_{uuid.uuid4().hex[:6]}"
    marker = "PLANTED_MARKER_OP_NEBULA_88341"

    # Turn 1 in Chat A: Plant marker
    res_a1 = ask_assistant(
        f"My secret project codename is {marker}. What store had highest revenue in 2025?",
        chat_id=chat_a,
    )
    assert res_a1["abstained"] is False
    assert "highest" in res_a1["answer"].lower() or "revenue" in res_a1["answer"].lower()

    # Query Chat B for the secret marker without mentioning the marker in Chat B
    res_b1 = ask_assistant("What is my secret project codename?", chat_id=chat_b)
    # Assistant must abstain or indicate no source covers this information
    assert marker not in res_b1["answer"]
    assert (
        res_b1["abstained"] is True
        or "cannot answer" in res_b1["answer"].lower()
        or "not mentioned" in res_b1["answer"].lower()
    )

    # Ask Chat B to summarize the discussion so far
    res_b2 = ask_assistant("Summarize what we discussed so far.", chat_id=chat_b)
    assert marker not in res_b2["answer"]
    assert "nebula" not in res_b2["answer"].lower()


def test_conversational_entity_isolation_across_chats():
    """Ensure resolved entity memo (e.g. 'that store' -> S04) does not leak from Chat A into Chat B."""
    chat_a = f"chat_A_{uuid.uuid4().hex[:6]}"
    chat_b = f"chat_B_{uuid.uuid4().hex[:6]}"

    # Turn 1 in Chat A: Establishes store S04
    t1_a = ask_assistant(
        "Which store had the highest revenue in 2025, and who manages it?", chat_id=chat_a
    )
    assert "Vikram Sethi" in t1_a["answer"]

    # Turn 1 in Chat B: Asks about a completely different topic (e.g. return window)
    t1_b = ask_assistant("What is the return window for Gold members?", chat_id=chat_b)
    assert "30" in t1_b["answer"]

    # Turn 2 in Chat B: Asks about 'that store' without ever mentioning a store in Chat B
    t2_b = ask_assistant(
        "Who were the top 3 customers by spend at that store in 2025?", chat_id=chat_b
    )
    # Chat B has no store in context; it must not resolve to S04 or Vikram Sethi
    assert t2_b.get("interpreted_as") is None or "S04" not in t2_b["interpreted_as"]
    # Chat B should not return Chat A's customer Aarav Kulkarni for that store
    assert "Aarav Kulkarni" not in t2_b["answer"]


def test_conversational_summarization_never_leaks_across_chats():
    """Assert Chat B summary strictly summarizes Chat B questions and contains zero Chat A content."""
    chat_a = f"chat_A_{uuid.uuid4().hex[:6]}"
    chat_b = f"chat_B_{uuid.uuid4().hex[:6]}"

    # Chat A turns: Store revenue and top customers
    ask_assistant("Which store had the highest revenue in 2025?", chat_id=chat_a)
    ask_assistant("Who were the top 3 customers by spend in 2025?", chat_id=chat_a)

    # Chat B turns: Return policies and warranty
    ask_assistant("What is the return window for Gold members?", chat_id=chat_b)
    ask_assistant("How many business days does a refund take?", chat_id=chat_b)

    # Summarize Chat B
    summary_b = ask_assistant("Summarize what we discussed so far.", chat_id=chat_b)
    ans_b = summary_b["answer"].lower()

    # Must contain Chat B topics
    assert "return window" in ans_b or "refund" in ans_b

    # Must NOT contain Chat A topics
    chat_a_forbidden = [
        "highest revenue",
        "top 3 customers",
        "connaught place",
        "ishaan sharma",
        "aarav kulkarni",
    ]
    for forbidden in chat_a_forbidden:
        assert forbidden not in ans_b, f"Chat B summary leaked Chat A topic: '{forbidden}'"


def test_chat_lifecycle_deletion_isolation():
    """Deleting Chat A must not delete or affect Chat B messages."""
    chat_a = create_chat("chat_to_delete", title="Temporary Chat")["chat_id"]
    chat_b = create_chat("chat_to_keep", title="Permanent Chat")["chat_id"]

    ask_assistant("What is the return window for Gold members?", chat_id=chat_a)
    ask_assistant("How many business days does a refund take?", chat_id=chat_b)

    assert len(get_chat_messages(chat_a)) >= 2
    assert len(get_chat_messages(chat_b)) >= 2

    # Delete Chat A
    delete_chat(chat_a)
    assert len(get_chat_messages(chat_a)) == 0
    # Chat B must remain intact
    assert len(get_chat_messages(chat_b)) >= 2


def test_first_question_chart_cross_chat_isolation():
    """Contextual referent 'first question' in Chat B must not adopt Chat A's first question (B9, R-056)."""
    chat_a = f"chat_A_{uuid.uuid4().hex[:6]}"
    chat_b = f"chat_B_{uuid.uuid4().hex[:6]}"

    # Turn 1 in Chat A: Establishes store revenue
    t1_a = ask_assistant(
        "Which store had the highest revenue in 2025, and who manages it?", chat_id=chat_a
    )
    assert t1_a["abstained"] is False

    # Turn 1 in Chat B: Asks for 'first question' chart in a brand new chat with no prior questions
    t1_b = ask_assistant(
        "Show the result of my first question as a bar chart of the top 5 stores.", chat_id=chat_b
    )
    # Must honestly abstain because Chat B has no prior question!
    assert t1_b["abstained"] is True
    assert (
        "no prior question" in t1_b["answer"].lower()
        or "cannot generate a chart" in t1_b["answer"].lower()
    )
    assert len(t1_b.get("charts", [])) == 0

    # Turn 2 in Chat A: Asks for 'first question' chart in Chat A (where Turn 1 exists)
    t2_a = ask_assistant(
        "Show the result of my first question as a bar chart of the top 5 stores.", chat_id=chat_a
    )
    assert t2_a["abstained"] is False
    assert len(t2_a.get("charts", [])) == 1
    assert t2_a["charts"][0]["chart_type"] == "bar"
