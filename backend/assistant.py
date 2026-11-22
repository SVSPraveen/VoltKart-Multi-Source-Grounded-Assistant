"""backend/assistant.py - Core assistant entrypoint.

Handles question answering by routing to the SQL agent, document retriever,
or web tool.

In Phase 1, this module is an unpopulated skeleton. It returns an empty
response to establish the verified RED BASELINE for golden evaluations.
"""

from __future__ import annotations

from typing import Any


def ask_assistant(
    question: str,
    chat_id: str = "default",
    web_enabled: bool = False,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Execute the multi-source QA pipeline for a user question.

    Returns a structured dictionary containing:
      - answer: str (the formatted assistant reply)
      - citations: list of structured citation records
      - abstained: bool (whether the assistant abstained)
      - chat_id: str
      - metadata: dict
    """
    # Phase 1: Skeleton only. Returns empty response so golden assertions fail.
    return {
        "answer": "",
        "citations": [],
        "abstained": False,
        "chat_id": chat_id,
        "metadata": {"phase": 1, "status": "skeleton"},
    }
