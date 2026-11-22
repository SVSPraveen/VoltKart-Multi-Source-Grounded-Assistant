"""tests/judge/test_judge_calibration.py - Calibrated Judge Verification Suite (V7).

Verifies:
1. Calibration requirement (spec section 10 & 15, R-016):
   - Feeds >= 5 deliberately wrong answers.
   - Asserts the judge flags >= 4 as FAILURES (asserts 5/5 flagged).
2. Discriminative validity:
   - Asserts genuine correct answers pass the judge rubric with score >= 0.70.
3. Produces calibrated evaluation outputs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.judge.calibrated_judge import CalibratedJudge

FIXTURES_PATH = Path(__file__).parent / "calibration_fixtures.json"


@pytest.fixture
def calibration_data() -> dict:
    with open(FIXTURES_PATH, encoding="utf-8") as f:
        return json.load(f)


def test_judge_calibration_flags_deliberate_errors(calibration_data: dict):
    """Calibrate first: feed >= 5 deliberately wrong answers; judge must flag >= 4 (R-016)."""
    judge = CalibratedJudge(pass_threshold=0.70)
    flawed_candidates = calibration_data["flawed_candidates"]
    assert len(flawed_candidates) >= 5, "Requires at least 5 flawed calibration fixtures"

    flagged_count = 0
    flagged_details: list[dict] = []

    for item in flawed_candidates:
        verdict = judge.evaluate(item["question_spec"], item["candidate_response"])
        is_flagged = not verdict.passed

        if is_flagged:
            flagged_count += 1

        flagged_details.append(
            {
                "id": item["id"],
                "expected_dimension": item.get("expected_failing_dimension"),
                "passed": verdict.passed,
                "overall_score": verdict.overall_score,
                "feedback": verdict.feedback,
            }
        )

    # Hard requirement: must flag >= 4 out of 5
    print(
        f"\nJudge Calibration Results: {flagged_count}/{len(flawed_candidates)} flawed candidates flagged."
    )
    assert flagged_count >= 4, (
        f"Judge failed calibration: only {flagged_count}/{len(flawed_candidates)} flagged (required >= 4)."
    )
    # Assert all 5 are caught
    assert flagged_count == 5, (
        f"Expected all 5 flawed candidates to be caught, but got {flagged_count}."
    )


def test_judge_accepts_correct_answers(calibration_data: dict):
    """Judge must not produce false rejections on valid answers."""
    judge = CalibratedJudge(pass_threshold=0.70)
    correct_candidates = calibration_data["correct_candidates"]

    for item in correct_candidates:
        verdict = judge.evaluate(item["question_spec"], item["candidate_response"])
        assert verdict.passed, (
            f"Judge falsely rejected valid candidate {item['id']}: {verdict.feedback}"
        )
        assert verdict.overall_score >= 0.70
