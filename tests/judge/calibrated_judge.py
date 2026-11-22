"""tests/judge/calibrated_judge.py - Calibrated LLM-and-Rule Judge Engine (V7).

Implements deterministic rubric evaluation over candidate assistant responses.
Computes dimensional scores for correctness, provenance, citation sufficiency,
abstention honesty, grounding faithfulness, and formatting.
"""

from __future__ import annotations

import re
from typing import Any

from tests.judge.rubric import DimensionScore, JudgeVerdict


def _extract_numbers(text: str) -> list[float]:
    """Extract numeric values from text after stripping currency signs and commas."""
    cleaned = re.sub(r"[₹$,]", "", text)
    tokens = re.findall(r"[-+]?\d*\.\d+|\b[-+]?\d+\b", cleaned)
    numbers: list[float] = []
    for tok in tokens:
        try:
            numbers.append(float(tok))
        except ValueError:
            continue
    return numbers


def _extract_expected_numbers(data: Any, prefix: str = "") -> list[tuple[str, float]]:
    """Recursively extract numeric expectations (amounts, counts, totals) from expected data structures."""
    numeric_items: list[tuple[str, float]] = []
    numeric_indicators = (
        "_inr",
        "count",
        "spend",
        "amount",
        "returns",
        "units",
        "total",
        "fee",
        "price",
        "revenue",
    )
    if isinstance(data, dict):
        for k, v in data.items():
            sub_key = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                if any(ind in str(k).lower() for ind in numeric_indicators) or isinstance(v, float):
                    numeric_items.append((sub_key, float(v)))
            elif isinstance(v, (dict, list)):
                numeric_items.extend(_extract_expected_numbers(v, prefix=sub_key))
    elif isinstance(data, list):
        for idx, item in enumerate(data):
            numeric_items.extend(_extract_expected_numbers(item, prefix=f"{prefix}[{idx}]"))
    return numeric_items


class CalibratedJudge:
    """Deterministic, rubric-based evaluation judge with calibration assertions (R-016)."""

    def __init__(self, pass_threshold: float = 0.70) -> None:
        self.pass_threshold = pass_threshold

    def evaluate(
        self, question_spec: dict[str, Any], candidate_response: dict[str, Any]
    ) -> JudgeVerdict:
        qid = str(question_spec.get("id", "custom"))
        answer_text = candidate_response.get("answer", "")
        citations = candidate_response.get("citations", [])
        is_abstained = candidate_response.get("abstained", False)

        dim_scores: dict[str, DimensionScore] = {}
        feedback: list[str] = []

        # 1. Dimension: Abstention Honesty (Weight: 0.20)
        exp_field = (
            str(question_spec.get("expect", "")) + " " + str(question_spec.get("expected", ""))
        )
        expect_abstain = (
            bool(question_spec.get("abstain", False))
            or "abstain" in exp_field.lower()
            or "refuse" in exp_field.lower()
            or "blocked" in exp_field.lower()
            or "no source" in exp_field.lower()
            or "no write" in exp_field.lower()
            or qid in {"A1", "A2", "A3", "A5", "A6", "A7"}
            or (question_spec.get("web") is False and question_spec.get("kind") == "web")
        )
        abstain_keywords = [
            "cannot answer",
            "not found",
            "no source",
            "not mentioned",
            "disabled",
            "does not contain",
            "unable to execute",
            "blocked",
            "cannot print",
            "cannot reveal",
            "cannot fulfill",
            "refuse",
            "unauthorized operation",
            "no write",
            "no 2027 orders",
            "no orders in 2027",
            "neither kavya",
            "which kavya",
            "multiple customers",
        ]
        text_suggests_abstain = any(k in answer_text.lower() for k in abstain_keywords)

        if expect_abstain:
            if is_abstained or text_suggests_abstain:
                dim_scores["abstention_honesty"] = DimensionScore(
                    name="abstention_honesty",
                    weight=0.20,
                    score=1.0,
                    passed=True,
                    reason="Correctly and honestly abstained when sources are absent or query is restricted.",
                )
            else:
                dim_scores["abstention_honesty"] = DimensionScore(
                    name="abstention_honesty",
                    weight=0.20,
                    score=0.0,
                    passed=False,
                    reason="Failed to abstain: generated ungrounded answer for out-of-scope query.",
                )
                feedback.append("Should have abstained honestly but attempted to answer.")
        else:
            if is_abstained and not question_spec.get("allow_abstain", False):
                dim_scores["abstention_honesty"] = DimensionScore(
                    name="abstention_honesty",
                    weight=0.20,
                    score=0.2,
                    passed=False,
                    reason="Unjustified abstention on answerable query.",
                )
                feedback.append("Abstained when ground truth data was available.")
            else:
                dim_scores["abstention_honesty"] = DimensionScore(
                    name="abstention_honesty",
                    weight=0.20,
                    score=1.0,
                    passed=True,
                    reason="Appropriate non-abstention on valid query.",
                )

        # 2. Dimension: Correctness vs Golden (Weight: 0.30)
        corr_score = 1.0
        corr_reasons: list[str] = []

        # Check numeric target
        tol = float(question_spec.get("tolerance", 0.01))
        nums = _extract_numbers(answer_text)
        expected_targets: list[tuple[str, float]] = []

        if "expected_number" in question_spec:
            expected_targets.append(("target", float(question_spec["expected_number"])))
        elif "expected" in question_spec and isinstance(question_spec["expected"], (dict, list)):
            expected_targets = _extract_expected_numbers(question_spec["expected"])

        if expected_targets:
            for lbl, target in expected_targets:
                matched = any(abs(n - target) <= max(tol, target * 0.001) for n in nums)
                if not matched:
                    deduct = min(0.5, 0.5 / len(expected_targets))
                    corr_score -= deduct
                    corr_reasons.append(
                        f"Expected number {target} for '{lbl}' (tol={tol}) not found in answer."
                    )
                    feedback.append(f"Numeric mismatch: {lbl}={target} missing.")

        # Check must_include
        must_include = question_spec.get("must_include", [])
        for item in must_include:
            if str(item).lower() not in answer_text.lower():
                corr_score -= 0.25
                corr_reasons.append(f"Required item '{item}' missing.")
                feedback.append(f"Missing required phrase: '{item}'")

        # Check must_not
        must_not = question_spec.get("must_not", [])
        for item in must_not:
            if str(item).lower() in answer_text.lower():
                corr_score -= 0.35
                corr_reasons.append(f"Forbidden item '{item}' detected.")
                feedback.append(f"Contained forbidden phrase: '{item}'")

        corr_score = max(0.0, min(1.0, corr_score))
        dim_scores["correctness"] = DimensionScore(
            name="correctness",
            weight=0.30,
            score=corr_score,
            passed=corr_score >= 0.70,
            reason="; ".join(corr_reasons)
            if corr_reasons
            else "All expected numbers and entities verified.",
        )

        # 3. Dimension: Provenance & Version Resolution (Weight: 0.20)
        prov_score = 1.0
        prov_reasons: list[str] = []
        expected_version = question_spec.get("expected_version") or question_spec.get(
            "must_state_version"
        )
        requires_fallback = (
            question_spec.get("requires_older_version", False)
            or bool(question_spec.get("must_state_version"))
            or "older" in str(question_spec.get("expect", "")).lower()
            or "older" in str(question_spec.get("expected", "")).lower()
            or "fallback" in str(question_spec.get("expected", "")).lower()
        )

        if expected_version:
            exp_str = str(expected_version).lower()
            in_text = exp_str in answer_text.lower()
            in_cit = any(
                exp_str in str(c.get("doc_date", "")).lower()
                or exp_str in str(c.get("date", "")).lower()
                or exp_str in str(c.get("version", "")).lower()
                or exp_str in str(c.get("file_name", "")).lower()
                or exp_str in str(c.get("source", "")).lower()
                for c in citations
            )
            if not (in_text or in_cit):
                prov_score -= 0.6
                prov_reasons.append(f"Expected version {expected_version} not cited or stated.")
                feedback.append(f"Provenance failure: version {expected_version} not cited.")

        if requires_fallback:
            fallback_indicators = [
                "note:",
                "stated in",
                "subsequent revision",
                "remains active",
                "older version",
                "superseded",
                "dated",
                "policy (",
                "version",
            ]
            has_fallback_note = any(ind in answer_text.lower() for ind in fallback_indicators)
            if not has_fallback_note:
                prov_score -= 0.4
                prov_reasons.append(
                    "Missing explicit fallback disclosure when answering from older version."
                )
                feedback.append("Failed to disclose fallback to older document version.")

        prov_score = max(0.0, min(1.0, prov_score))
        dim_scores["provenance"] = DimensionScore(
            name="provenance",
            weight=0.20,
            score=prov_score,
            passed=prov_score >= 0.70,
            reason="; ".join(prov_reasons)
            if prov_reasons
            else "Version provenance and fallback disclosure verified.",
        )

        # 4. Dimension: Citation Sufficiency (Weight: 0.15)
        cit_score = 1.0
        cit_reasons: list[str] = []
        is_summary = (
            question_spec.get("kind") == "summary"
            or "summarize" in question_spec.get("question", "").lower()
            or qid in {"Q20", "A5", "A6", "A7"}
        )

        if not expect_abstain and not is_abstained and not is_summary:
            if not citations:
                cit_score = 0.0
                cit_reasons.append("Zero citations provided for supported claim.")
                feedback.append("Citations missing completely.")
            else:
                for c in citations:
                    c_type = c.get("type", "unknown")
                    if c_type == "table":
                        if not c.get("sql") and not c.get("tables"):
                            cit_score -= 0.3
                            cit_reasons.append("Table citation missing executed SQL.")
                    elif c_type == "document":
                        if not c.get("verbatim_quote") and not c.get("quote"):
                            cit_score -= 0.3
                            cit_reasons.append("Document citation missing verbatim quote.")
                    elif c_type == "web":
                        if not c.get("url"):
                            cit_score -= 0.3
                            cit_reasons.append("Web citation missing source URL.")

        cit_score = max(0.0, min(1.0, cit_score))
        dim_scores["citation_sufficiency"] = DimensionScore(
            name="citation_sufficiency",
            weight=0.15,
            score=cit_score,
            passed=cit_score >= 0.70,
            reason="; ".join(cit_reasons)
            if cit_reasons
            else "Sufficient structured citations present.",
        )

        # 5. Dimension: Grounding & No Hallucination (Weight: 0.10)
        ground_score = 1.0
        ground_reasons: list[str] = []

        # Check for fabricated delivery date (R-007)
        if re.search(
            r"(?:delivered\s+on|delivery\s+date\s*(?:is|was|of)?)\s*\d{4}-\d{2}-\d{2}",
            answer_text,
            re.I,
        ):
            ground_score -= 0.6
            ground_reasons.append(
                "Fabricated specific delivery date not present in orders data (R-007)."
            )
            feedback.append("Fabricated delivery date detected.")

        dim_scores["grounding_faithfulness"] = DimensionScore(
            name="grounding_faithfulness",
            weight=0.10,
            score=ground_score,
            passed=ground_score >= 0.70,
            reason="; ".join(ground_reasons)
            if ground_reasons
            else "No ungrounded or fabricated claims detected.",
        )

        # 6. Dimension: Formatting & Tone (Weight: 0.05)
        format_score = 1.0
        format_reasons: list[str] = []

        # Currency formatting check for financial answers
        if any(
            w in question_spec.get("question", "").lower()
            for w in ["revenue", "spend", "refund", "amount", "price"]
        ):
            if (
                "₹" not in answer_text
                and "inr" not in answer_text.lower()
                and "rs" not in answer_text.lower()
            ):
                format_score -= 0.3
                format_reasons.append("Monetary values lack ₹ or INR currency symbol.")

        dim_scores["formatting_tone"] = DimensionScore(
            name="formatting_tone",
            weight=0.05,
            score=format_score,
            passed=format_score >= 0.70,
            reason="; ".join(format_reasons)
            if format_reasons
            else "Clean professional formatting.",
        )

        # Calculate overall weighted score
        overall_score = sum(dim.score * dim.weight for dim in dim_scores.values())
        is_passed = (
            overall_score >= self.pass_threshold
            and dim_scores["correctness"].passed
            and dim_scores["provenance"].passed
            and dim_scores["citation_sufficiency"].passed
            and dim_scores["abstention_honesty"].passed
            and dim_scores["grounding_faithfulness"].passed
        )

        return JudgeVerdict(
            question_id=qid,
            passed=is_passed,
            overall_score=overall_score,
            dimension_scores=dim_scores,
            feedback=feedback,
            raw_response=candidate_response,
        )
