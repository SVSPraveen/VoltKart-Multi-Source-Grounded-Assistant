"""scripts/run_core_evals.py - Core Complete Gate Evaluation Runner.

Executes Golden Questions Q1–Q14 and Q20 across 3 consecutive live runs.
Evaluates deterministic assertions (numeric tolerance within 0.01, entity inclusion/exclusion,
citation fields, version statements, abstention).
Prints a formatted per-question summary table asserting 3/3 pass rate.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.assistant import ask_assistant  # noqa: E402
from backend.storage import init_sqlite_db, reset_storage  # noqa: E402
from tests.golden.eval_harness import evaluate_response, load_golden_specs  # noqa: E402


def run_single_eval_cycle(run_number: int, questions_to_run: list[dict]) -> dict[int, bool]:
    """Execute one complete cycle of golden questions in their specified chat contexts."""
    # Reset storage to start fresh for each eval cycle
    reset_storage()
    init_sqlite_db()

    results: dict[int, bool] = {}

    for q_spec in questions_to_run:
        qid = q_spec["id"]
        chat_id = f"chat_{q_spec.get('chat', 1)}"
        web_enabled = bool(q_spec.get("web", False))

        # Check if question requires backend restart before running (Q20)
        if q_spec.get("restart_backend_before", False):
            # Simulate backend restart: reinitialize storage structures from disk
            init_sqlite_db()

        try:
            response = ask_assistant(
                question=q_spec["question"],
                chat_id=chat_id,
                web_enabled=web_enabled,
            )
            evaluate_response(response, q_spec)
            results[qid] = True
        except Exception as exc:
            print(f"Run {run_number} - Question Q{qid} FAILED: {exc}")
            results[qid] = False

    return results


def main():
    specs = load_golden_specs()
    all_questions = specs.get("questions", [])

    # Filter to Core Questions: Q1-Q14 and Q20
    core_ids = set(range(1, 15)) | {20}
    core_questions = [q for q in all_questions if q["id"] in core_ids]

    print("\n=======================================================")
    print("  CORE COMPLETE GATE: Live Evaluation (3 consecutive runs)")
    print(f"  Questions: Q1–Q14 and Q20 ({len(core_questions)} questions)")
    print("=======================================================\n")

    runs_results: list[dict[int, bool]] = []
    for r in range(1, 4):
        print(f"--- Starting Run {r}/3 ---")
        run_res = run_single_eval_cycle(r, core_questions)
        runs_results.append(run_res)
        pass_count = sum(1 for v in run_res.values() if v)
        print(f"--- Run {r}/3 Finished: {pass_count}/{len(core_questions)} passed ---\n")

    # Compile Summary Table
    print("+----------+-------+-------+-------+-------------+")
    print("| Question | Run 1 | Run 2 | Run 3 | Total (3/3) |")
    print("+----------+-------+-------+-------+-------------+")

    all_passed = True
    for q_spec in core_questions:
        qid = q_spec["id"]
        r1 = "PASS" if runs_results[0].get(qid) else "FAIL"
        r2 = "PASS" if runs_results[1].get(qid) else "FAIL"
        r3 = "PASS" if runs_results[2].get(qid) else "FAIL"
        passed_3_of_3 = r1 == "PASS" and r2 == "PASS" and r3 == "PASS"
        status_label = "PASS (3/3)" if passed_3_of_3 else "FAIL"
        if not passed_3_of_3:
            all_passed = False

        print(f"| Q{qid:<8} | {r1:<5} | {r2:<5} | {r3:<5} | {status_label:<11} |")

    print("+----------+-------+-------+-------+-------------+\n")

    if all_passed:
        print("[RESULT] CORE COMPLETE GATE: ALL 15 CORE QUESTIONS PASSED 3/3 LIVE RUNS!")
        sys.exit(0)
    else:
        print("[FAIL] Some questions failed to achieve 3/3 pass rate.")
        sys.exit(1)


if __name__ == "__main__":
    main()
