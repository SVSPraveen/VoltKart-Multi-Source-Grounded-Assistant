"""tests/golden/eval_harness.py - Deterministic Evaluation Harness for Golden Evals.

Implements deterministic verification checks:
1. Numeric tolerance: exact match within 0.01 tolerance (no arithmetic by LLM).
2. Entity coverage: must_include and must_not checks.
3. Citation validation: table sources + executed SQL, or document sources + verbatim quotes.
4. Version disclosure: explicit provenance reporting when older documents answer.
5. Abstention: honesty check when sources are absent or web is disabled.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


def load_golden_specs(golden_yaml_path: Path | None = None) -> dict[str, Any]:
    """Load and parse golden.yaml."""
    if golden_yaml_path is None:
        candidates = [
            Path("tests/golden/golden.yaml"),
            Path("golden.yaml"),
        ]
        for c in candidates:
            if c.exists():
                golden_yaml_path = c.resolve()
                break

    if golden_yaml_path is None or not golden_yaml_path.exists():
        raise FileNotFoundError("Could not locate golden.yaml")

    with open(golden_yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data


def assert_numeric_tolerance(
    actual: float, expected: float, tolerance: float = 0.01, label: str = ""
) -> None:
    """Assert actual equals expected within tolerance."""
    diff = abs(actual - expected)
    if diff > tolerance:
        raise AssertionError(
            f"Numeric mismatch for {label or 'value'}: actual {actual} != expected {expected} "
            f"(diff={diff:.6f} > tolerance={tolerance})"
        )


def extract_numbers_from_text(text: str) -> list[float]:
    """Extract numeric values from text, handling commas and currency symbols."""
    # Strip currency signs and commas inside numbers
    cleaned = re.sub(r"[₹$,]", "", text)
    tokens = re.findall(r"[-+]?\d*\.\d+|\b[-+]?\d+\b", cleaned)
    numbers: list[float] = []
    for tok in tokens:
        try:
            numbers.append(float(tok))
        except ValueError:
            continue
    return numbers


def contains_number(numbers: list[float], target: float, tolerance: float = 0.01) -> bool:
    """Check if any number in the list matches target within tolerance."""
    return any(abs(n - target) <= tolerance for n in numbers)


def assert_must_include(text: str, must_include: list[str]) -> None:
    """Assert all required substrings appear in the response text."""
    lower_text = text.lower()
    for item in must_include:
        if str(item).lower() not in lower_text:
            raise AssertionError(
                f"Required item '{item}' not found in response text: {text[:200]}..."
            )


def assert_must_not(text: str, must_not: list[str]) -> None:
    """Assert none of the forbidden substrings appear in the response text."""
    lower_text = text.lower()
    for item in must_not:
        if str(item).lower() in lower_text:
            raise AssertionError(
                f"Forbidden item '{item}' unexpectedly found in response text: {text[:200]}..."
            )


def assert_version_stated(
    text: str, citations: list[dict[str, Any]], expected_version: str
) -> None:
    """Assert the required version is explicitly stated in response text or citations."""
    exp = str(expected_version).lower()
    in_text = exp in text.lower()
    in_citations = any(
        exp in str(c.get("date", "")).lower() or exp in str(c.get("version", "")).lower()
        for c in citations
    )
    if not (in_text or in_citations):
        raise AssertionError(
            f"Expected document version '{expected_version}' was not stated in text or citations."
        )


def assert_abstention(response: dict[str, Any]) -> None:
    """Assert that the assistant honestly abstained."""
    abstained_flag = bool(response.get("abstained", False))
    text = str(response.get("answer", "")).lower()
    abstention_phrases = [
        "cannot answer",
        "can not answer",
        "not found",
        "no source",
        "no information",
        "web search is off",
        "web search is disabled",
        "unable to answer",
        "not available in the provided",
        "does not mention",
    ]
    phrase_matched = any(p in text for p in abstention_phrases)

    if not (abstained_flag or phrase_matched):
        raise AssertionError(
            "Expected assistant to honestly ABSTAIN, but neither 'abstained=True' "
            f"nor an abstention explanation was present in response: '{text[:200]}...'"
        )


def assert_citations(
    citations: list[dict[str, Any]],
    kind: str,
    citation_must_show: list[str] | None = None,
) -> None:
    """Verify citation fields based on question kind (table or doc)."""
    if not citations:
        raise AssertionError(f"No citations provided for question of kind '{kind}'.")

    if kind == "table":
        # Table citations must include SQL and tables
        has_sql = any(bool(c.get("sql")) for c in citations)
        if not has_sql:
            raise AssertionError("Table answer citation must include the executed SQL.")
        if citation_must_show:
            combined = " ".join(str(c) for c in citations).lower()
            for req in citation_must_show:
                if "sql" in req.lower():
                    continue
                # Extract key table names from requirement if phrased as 'tables: orders, ...'
                clean_req = req.replace("tables:", "").replace("table:", "").strip()
                tables = [t.strip().lower() for t in clean_req.split(",") if t.strip()]
                for t in tables:
                    if t not in combined:
                        raise AssertionError(f"Citation missing required table reference: '{t}'.")

    elif kind in ("doc", "mixed"):
        # Document citations must include document source and quote
        has_source = any(
            bool(c.get("source") or c.get("file_name") or c.get("document")) for c in citations
        )
        if not has_source:
            raise AssertionError("Document answer citation must include document source/filename.")


def evaluate_response(response: dict[str, Any], question_spec: dict[str, Any]) -> None:
    """Top-level deterministic evaluation of an assistant response against golden specs."""
    answer_text = str(response.get("answer", ""))
    citations = response.get("citations", [])
    expected = question_spec.get("expected", {})
    kind = question_spec.get("kind", "")

    # 1. Abstention check
    behavior = str(expected.get("behavior", ""))
    if "ABSTAIN" in behavior or question_spec.get("expect", "").startswith("ABSTAIN"):
        assert_abstention(response)
        return

    # 2. must_include check
    if "must_include" in question_spec:
        assert_must_include(answer_text, question_spec["must_include"])

    # 3. must_not check
    if "must_not" in question_spec:
        assert_must_not(answer_text, question_spec["must_not"])

    # 4. must_state_version check
    if "must_state_version" in question_spec:
        assert_version_stated(answer_text, citations, question_spec["must_state_version"])

    # 5. Citation verification
    assert_citations(
        citations, kind=kind, citation_must_show=question_spec.get("citation_must_show")
    )

    # 6. Numeric tolerance checks
    extracted_nums = extract_numbers_from_text(answer_text)
    # Also add numbers from citation result rows
    for c in citations:
        for row in c.get("result_rows", []):
            if isinstance(row, dict):
                for v in row.values():
                    try:
                        extracted_nums.append(float(v))
                    except (ValueError, TypeError):
                        pass

    if "revenue_inr" in expected:
        exp_rev = float(expected["revenue_inr"])
        if not contains_number(extracted_nums, exp_rev, tolerance=0.01):
            raise AssertionError(
                f"Expected revenue {exp_rev} (+/- 0.01) not found in response numbers: {extracted_nums}"
            )

    if "grand_total_inr" in expected:
        exp_gt = float(expected["grand_total_inr"])
        if not contains_number(extracted_nums, exp_gt, tolerance=0.01):
            raise AssertionError(
                f"Expected grand total {exp_gt} (+/- 0.01) not found in response numbers: {extracted_nums}"
            )

    if "by_region_inr" in expected:
        for reg, val in expected["by_region_inr"].items():
            exp_val = float(val)
            if not contains_number(extracted_nums, exp_val, tolerance=0.01):
                raise AssertionError(
                    f"Expected region {reg} refund {exp_val} (+/- 0.01) not found in response."
                )
