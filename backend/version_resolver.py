"""backend/version_resolver.py - Deterministic version resolver and quote verifier.

Implements Spec Section 7.3 & REVIEW R-001, R-006, R-017, R-019:
1. Code-enforced verbatim quote verification: evidence_quote must be an exact normalized
   substring of the chunk content, otherwise the extraction is discarded.
2. Deterministic claim-level resolution: among versions that state the fact with verified quotes,
   picks the latest document date. Never filters by date at retrieval time.
3. Fallback disclosure: if newer versions exist in the family but are silent, flags fallback_used=True,
   records newer silent versions, and compiles superseded values for evidence provenance.
4. Tie date handling: equal latest dates with conflicting facts are flagged as ties without guessing.
5. Point-in-time as-of date resolution: resolves facts in force as of an explicit historical date.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field


def normalize_text_for_quote_match(text: str) -> str:
    """Normalize whitespace and punctuation characters for verbatim quote comparison."""
    if not text:
        return ""
    # Collapse any whitespace / newline sequence to single space
    cleaned = re.sub(r"\s+", " ", text)
    # Normalize curly/directional quotes and dashes
    cleaned = cleaned.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    cleaned = cleaned.replace("—", "-").replace("–", "-")
    return cleaned.strip().lower()


def verify_verbatim_quote(evidence_quote: str | None, chunk_content: str | None) -> bool:
    """Strictly verify that evidence_quote is a normalized substring of chunk_content (R-019)."""
    if not evidence_quote or not chunk_content:
        return False
    norm_quote = normalize_text_for_quote_match(evidence_quote).strip("'\"")
    norm_content = normalize_text_for_quote_match(chunk_content)
    if not norm_quote:
        return False
    return norm_quote in norm_content


class ExtractedClaim(BaseModel):
    """Candidate fact extracted from a single document version."""

    file_name: str
    doc_date: str | None = None
    version_family: str = ""
    section: str = ""
    page: int | None = None
    states_fact: bool = False
    value: str | None = None
    evidence_quote: str | None = None
    quote_verified: bool = False
    chunk_id: str = ""
    chunk_content: str = ""


class ResolvedFact(BaseModel):
    """The deterministically resolved fact across all versions in a document family."""

    fact_name: str
    winner: ExtractedClaim | None = None
    status: str = "answered"  # "answered", "fallback", "tie_dates", "out_of_coverage", "abstained"
    fallback_used: bool = False
    newer_silent_versions: list[str] = Field(default_factory=list)
    superseded: list[dict[str, Any]] = Field(default_factory=list)
    version_timeline: list[dict[str, Any]] = Field(default_factory=list)
    explanation: str = ""


def _sort_key_for_date(doc_date: str | None) -> tuple[int, str]:
    """Helper to sort dates chronologically, ranking dated documents above undated (R-017)."""
    if doc_date:
        return (1, doc_date)
    return (0, "0000-00-00")


def resolve_fact_across_versions(
    claims: list[ExtractedClaim],
    family_files: list[dict[str, Any]] | None = None,
    as_of_date: str | None = None,
    fact_name: str = "fact",
) -> ResolvedFact:
    """Deterministically resolve a single fact across candidate version extractions."""
    family_files = family_files or []

    # 1. Enforce code-level verbatim quote verification (R-019)
    verified_claims: list[ExtractedClaim] = []
    for c in claims:
        if c.states_fact and c.evidence_quote:
            is_valid = verify_verbatim_quote(c.evidence_quote, c.chunk_content)
            c.quote_verified = is_valid
            if not is_valid:
                c.states_fact = False
        else:
            c.quote_verified = False
        verified_claims.append(c)

    # 2. Handle point-in-time as_of date constraints (e.g. Probe A3, Probe A4)
    eligible_family_files = family_files
    eligible_claims = verified_claims

    if as_of_date:
        # Check if as_of_date is before the earliest dated document in the family
        dated_files = [f for f in family_files if f.get("doc_date")]
        if dated_files:
            earliest_file = min(dated_files, key=lambda f: f["doc_date"])
            earliest_date = earliest_file["doc_date"]
            if as_of_date < earliest_date:
                return ResolvedFact(
                    fact_name=fact_name,
                    winner=None,
                    status="out_of_coverage",
                    fallback_used=False,
                    explanation=(
                        f"No available source covers {as_of_date}. "
                        f"The earliest available policy document is dated {earliest_date}."
                    ),
                )

        # Filter to versions in force on or before as_of_date
        eligible_family_files = [
            f for f in family_files if f.get("doc_date") and f["doc_date"] <= as_of_date
        ]
        eligible_claims = [c for c in verified_claims if c.doc_date and c.doc_date <= as_of_date]

    # 3. Filter to claims that explicitly state the fact with verified quotes
    stating_claims = [c for c in eligible_claims if c.states_fact and c.quote_verified and c.value]

    if not stating_claims:
        return ResolvedFact(
            fact_name=fact_name,
            winner=None,
            status="abstained",
            fallback_used=False,
            explanation="The requested information is not stated in any uploaded document.",
        )

    # 4. Sort stating claims chronologically (undated documents rank last per R-017)
    stating_claims.sort(key=lambda c: _sort_key_for_date(c.doc_date))

    # 5. Check for tie dates on the latest stating claims
    latest_date = stating_claims[-1].doc_date
    latest_claims = [c for c in stating_claims if c.doc_date == latest_date]

    if len(latest_claims) > 1:
        # Check if latest claims conflict in value
        norm_values = {normalize_text_for_quote_match(c.value or "") for c in latest_claims}
        if len(norm_values) > 1:
            return ResolvedFact(
                fact_name=fact_name,
                winner=None,
                status="tie_dates",
                fallback_used=False,
                explanation=f"Conflicting values found in multiple documents dated {latest_date}.",
            )

    # Winner is the stating claim with the latest document date
    winner = stating_claims[-1]

    # 6. Record superseded values from older stating versions
    superseded_list: list[dict[str, Any]] = []
    for c in stating_claims[:-1]:
        if c.doc_date and c.doc_date != winner.doc_date:
            superseded_list.append(
                {
                    "doc_date": c.doc_date,
                    "file_name": c.file_name,
                    "value": c.value,
                    "quote": c.evidence_quote,
                    "section": c.section,
                }
            )

    # 7. Check for fallback: do newer versions exist in the family that are silent? (R-001)
    fallback_used = False
    newer_silent: list[str] = []

    if winner.doc_date:
        for f in eligible_family_files:
            f_date = f.get("doc_date")
            if f_date and f_date > winner.doc_date:
                fallback_used = True
                newer_silent.append(f["file_name"])

    # 8. Build full version timeline for evidence drawer
    timeline: list[dict[str, Any]] = []
    seen_files: set[str] = set()

    # Add stating claims to timeline
    for c in stating_claims:
        is_winner = c.chunk_id == winner.chunk_id
        timeline.append(
            {
                "file_name": c.file_name,
                "doc_date": c.doc_date or "undated",
                "status": "winner" if is_winner else "superseded",
                "value": c.value,
                "quote": c.evidence_quote,
            }
        )
        seen_files.add(c.file_name)

    # Add silent versions to timeline
    for f in eligible_family_files:
        fn = f["file_name"]
        if fn not in seen_files:
            timeline.append(
                {
                    "file_name": fn,
                    "doc_date": f.get("doc_date") or "undated",
                    "status": "silent",
                    "value": None,
                    "quote": None,
                }
            )
            seen_files.add(fn)

    timeline.sort(
        key=lambda t: (0, t["doc_date"]) if t["doc_date"] != "undated" else (1, "9999-99-99")
    )

    return ResolvedFact(
        fact_name=fact_name,
        winner=winner,
        status="fallback" if fallback_used else "answered",
        fallback_used=fallback_used,
        newer_silent_versions=newer_silent,
        superseded=superseded_list,
        version_timeline=timeline,
    )
