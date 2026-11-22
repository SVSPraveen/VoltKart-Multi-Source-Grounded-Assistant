"""scripts/run_phase4_eval.py - Phase 4 Live Evaluation Runner.

Executes Golden Questions Q6-Q12 three times each and Adversarial Probes A1-A5.
Evaluates deterministic assertions and prints evidence drawer details for Q8, Q9, Q11, Q12.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.assistant import ask_assistant  # noqa: E402
from tests.golden.eval_harness import (  # noqa: E402
    evaluate_adversarial_probe,
    evaluate_response,
    load_golden_specs,
)


def run_phase4_live_evals() -> None:
    specs = load_golden_specs()
    all_questions = {q["id"]: q for q in specs.get("questions", [])}
    all_probes = {p["id"]: p for p in specs.get("adversarial_probes", [])}

    target_qids = [6, 7, 8, 9, 10, 11, 12]
    target_probes = ["A1", "A2", "A3", "A4", "A5"]

    print("=" * 80)
    print("PHASE 4: LIVE GOLDEN EVALUATIONS (Q6 - Q12) - 3 RUNS EACH")
    print("=" * 80)

    summary_results: list[dict] = []

    for qid in target_qids:
        q_spec = all_questions[qid]
        q_text = q_spec["question"]
        runs = []
        last_resp = None

        print(f'\n--- Question Q{qid}: "{q_text}" ---')
        for run_idx in range(1, 4):
            chat_id = f"eval_q{qid}_run{run_idx}"
            resp = ask_assistant(q_text, chat_id=chat_id, web_enabled=False)
            last_resp = resp
            try:
                evaluate_response(resp, q_spec)
                status = "PASS"
                err = ""
            except Exception as e:
                status = "FAIL"
                err = str(e)
            runs.append((status, err))
            print(f"  Run {run_idx}: {status} {f'({err})' if err else ''}")

        all_passed = all(s == "PASS" for s, _ in runs)
        summary_results.append(
            {
                "id": f"Q{qid}",
                "question": q_text,
                "runs": [s for s, _ in runs],
                "all_passed": all_passed,
                "answer": last_resp["answer"] if last_resp else "",
                "citations": last_resp.get("citations", []) if last_resp else [],
            }
        )

        # Detailed evidence drawer for Q8, Q9, Q11, Q12
        if qid in [8, 9, 11, 12] and last_resp:
            print("\n  [EVIDENCE DRAWER]")
            for idx, c in enumerate(last_resp.get("citations", [])):
                print(f"  Citation #{idx + 1}:")
                print(
                    f"    Answered by: {c.get('file_name')} (Date: {c.get('doc_date')}, Section: {c.get('section')}, Page: {c.get('page')})"
                )
                print(f'    Verbatim Quote: "{c.get("verbatim_quote")}"')
                print(f"    Fallback Used: {c.get('fallback_used')}")
                print(f"    Newer Silent Versions: {c.get('newer_silent_versions')}")
                print(f"    Superseded Versions: {c.get('superseded')}")
                version_stated = (
                    (c.get("doc_date") in last_resp["answer"]) if c.get("doc_date") else False
                )
                print(f"    Answer Stated Version: {version_stated}")

    print("\n" + "=" * 80)
    print("PHASE 4: ADVERSARIAL PROBES (A1 - A5)")
    print("=" * 80)

    probe_results: list[dict] = []
    for pid in target_probes:
        p_spec = all_probes[pid]
        p_text = p_spec["question"]
        print(f'\n--- Probe {pid}: "{p_text}" ---')
        resp = ask_assistant(p_text, chat_id=f"probe_{pid}", web_enabled=False)
        try:
            evaluate_adversarial_probe(resp, p_spec)
            status = "PASS"
            err = ""
        except Exception as e:
            status = "FAIL"
            err = str(e)
        print(f"  Result: {status} {f'({err})' if err else ''}")
        print(f"  Answer: {resp['answer']}")
        print(f"  Abstained: {resp.get('abstained')}")
        probe_results.append(
            {
                "id": pid,
                "question": p_text,
                "status": status,
                "answer": resp["answer"],
                "abstained": resp.get("abstained"),
            }
        )

    print("\n" + "=" * 80)
    print("PHASE 4 SUMMARY TABLE")
    print("=" * 80)
    print(f"{'Question':<8} | {'Run 1':<6} | {'Run 2':<6} | {'Run 3':<6} | {'Status':<6}")
    print("-" * 42)
    for res in summary_results:
        r1, r2, r3 = res["runs"]
        status = "PASS" if res["all_passed"] else "FAIL"
        print(f"{res['id']:<8} | {r1:<6} | {r2:<6} | {r3:<6} | {status:<6}")
    print("-" * 42)
    for p in probe_results:
        print(f"{p['id']:<8} | {p['status']:<6} | {'-':<6} | {'-':<6} | {p['status']:<6}")
    print("=" * 80)


if __name__ == "__main__":
    run_phase4_live_evals()
