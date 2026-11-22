"""tests/golden/test_golden.py - Golden Evaluation Test Suite.

Wired directly to tests/golden/golden.yaml.
Executes questions through the assistant interface and evaluates with
deterministic assertions:
- Numeric tolerance (0.01)
- Entity inclusion (must_include) and exclusion (must_not)
- Citation requirements (table SQL, document provenance)
- Version statement
- Abstention behavior
"""

from __future__ import annotations

import pytest

from backend.assistant import ask_assistant
from tests.golden.eval_harness import evaluate_response, load_golden_specs

# Load golden questions from tests/golden/golden.yaml
GOLDEN_DATA = load_golden_specs()
QUESTIONS = GOLDEN_DATA.get("questions", [])
PROBES = GOLDEN_DATA.get("adversarial_probes", [])


@pytest.mark.parametrize("question_spec", QUESTIONS, ids=[f"Q{q['id']}" for q in QUESTIONS])
def test_golden_question(question_spec: dict):
    """Run golden question through assistant and assert deterministic evaluation."""
    chat_id = f"chat_{question_spec.get('chat', 1)}"
    web_enabled = bool(question_spec.get("web", False))

    response = ask_assistant(
        question=question_spec["question"],
        chat_id=chat_id,
        web_enabled=web_enabled,
    )

    evaluate_response(response, question_spec)


@pytest.mark.parametrize("probe_spec", PROBES, ids=[p["id"] for p in PROBES])
def test_adversarial_probe(probe_spec: dict):
    """Run adversarial probe through assistant and verify expected behavior/abstention."""
    response = ask_assistant(
        question=probe_spec["question"],
        chat_id="adversarial_probe_chat",
        web_enabled=False,
    )

    evaluate_response(response, probe_spec)
