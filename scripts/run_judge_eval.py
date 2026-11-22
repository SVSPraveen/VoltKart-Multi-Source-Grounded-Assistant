"""scripts/run_judge_eval.py - Calibrated Judge Golden Evaluation Runner (V7).

Runs all Golden Questions through the assistant and evaluates every output
against the Calibrated Judge rubric across 6 dimensions:
- Correctness vs golden
- Provenance (right version, stated when fallback)
- Citation sufficiency
- Abstention honesty
- Grounding faithfulness (no hallucinations)
- Professional formatting & tone

Outputs JSON report to reports/judge_evaluation.json and markdown summary.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.assistant import ask_assistant  # noqa: E402
from backend.storage import init_sqlite_db  # noqa: E402
from tests.golden.eval_harness import load_golden_specs  # noqa: E402
from tests.judge.calibrated_judge import CalibratedJudge  # noqa: E402
from tests.unit.test_sample_bundle_ingestion import test_full_sample_bundle_ingestion  # noqa: E402


def main() -> int:
    specs = load_golden_specs()
    questions = specs.get("questions", [])
    probes = specs.get("adversarial_probes", [])

    judge = CalibratedJudge(pass_threshold=0.70)
    print("Ingesting sample bundle to ensure fresh grounded state...")
    test_full_sample_bundle_ingestion()
    init_sqlite_db()

    print("\n" + "=" * 80)
    print("PHASE 7 - V7 CALIBRATED JUDGE EVALUATION")
    print("=" * 80)

    verdicts: list[dict] = []
    passed_count = 0
    total_evaluated = 0

    print(f"\nEvaluating {len(questions)} Golden Questions + {len(probes)} Adversarial Probes...")

    # 1. Evaluate Golden Questions
    for q in questions:
        total_evaluated += 1
        qid = f"Q{q['id']}"
        chat_id = f"chat_{q.get('chat', 1)}"
        web_enabled = bool(q.get("web", False))

        if q.get("restart_backend_before", False):
            init_sqlite_db()

        if "turns" in q:
            response = None
            for turn in q["turns"]:
                response = ask_assistant(
                    question=turn["question"],
                    chat_id=chat_id,
                    web_enabled=bool(turn.get("web", web_enabled)),
                )
        else:
            response = ask_assistant(
                question=q["question"],
                chat_id=chat_id,
                web_enabled=web_enabled,
            )

        verdict = judge.evaluate(q, response)
        verdicts.append(verdict.to_dict())

        st = "PASS" if verdict.passed else "FAIL"
        if verdict.passed:
            passed_count += 1
        print(f"  [{st}] {qid:<5} (Score: {verdict.overall_score:.2f}) - {q['question'][:50]}...")
        if not verdict.passed:
            print(f"         Feedback: {verdict.feedback}")

    # 2. Evaluate Probes
    for p in probes:
        total_evaluated += 1
        pid = str(p["id"])
        response = ask_assistant(
            question=p["question"],
            chat_id="adversarial_probe_chat",
            web_enabled=False,
        )
        verdict = judge.evaluate(p, response)
        verdicts.append(verdict.to_dict())

        st = "PASS" if verdict.passed else "FAIL"
        if verdict.passed:
            passed_count += 1
        print(f"  [{st}] {pid:<5} (Score: {verdict.overall_score:.2f}) - {p['question'][:50]}...")
        if not verdict.passed:
            print(f"         Feedback: {verdict.feedback}")

    pass_rate = (passed_count / total_evaluated) * 100.0
    print("\n" + "-" * 80)
    print(f"Calibrated Judge Summary: {passed_count}/{total_evaluated} Passed ({pass_rate:.1f}%)")
    print("-" * 80)

    # Save reports
    reports_dir = ROOT_DIR / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    json_path = reports_dir / "judge_evaluation.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()),
                "total_evaluated": total_evaluated,
                "passed_count": passed_count,
                "pass_rate_pct": round(pass_rate, 1),
                "verdicts": verdicts,
            },
            f,
            indent=2,
        )

    # Markdown summary
    md_path = reports_dir / f"judge_evaluation_{time.strftime('%Y%m%d_%H%M%S')}.md"
    md_lines = [
        "# Calibrated Judge Evaluation Report (V7)",
        f"- Timestamp: {time.strftime('%Y-%m-%d %H:%M:%SZ', time.gmtime())}",
        f"- Total Evaluated: {total_evaluated}",
        f"- Passed: {passed_count} ({pass_rate:.1f}%)",
        "",
        "## Summary Table",
        "| ID | Score | Status | Correctness | Provenance | Citations | Abstention | Grounding |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]
    for v in verdicts:
        dims = v["dimensions"]
        c_st = "OK" if dims["correctness"]["passed"] else "FAIL"
        p_st = "OK" if dims["provenance"]["passed"] else "FAIL"
        cit_st = "OK" if dims["citation_sufficiency"]["passed"] else "FAIL"
        a_st = "OK" if dims["abstention_honesty"]["passed"] else "FAIL"
        g_st = "OK" if dims["grounding_faithfulness"]["passed"] else "FAIL"
        status_md = "**PASS**" if v["passed"] else "**FAIL**"
        md_lines.append(
            f"| `{v['question_id']}` | {v['overall_score']:.2f} | {status_md} | {c_st} | {p_st} | {cit_st} | {a_st} | {g_st} |"
        )

    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"Reports saved to:\n  - {json_path}\n  - {md_path}")

    return 0 if passed_count == total_evaluated else 1


if __name__ == "__main__":
    sys.exit(main())
