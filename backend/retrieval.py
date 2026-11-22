"""backend/retrieval.py - Hybrid document retrieval and sibling expansion.

Implements Spec Section 7.3.1:
1. Hybrid search across ALL versions: SQLite FTS5 BM25 + local ONNX embeddings fused
   with Reciprocal Rank Fusion (RRF). Never pre-filters by date.
2. Sibling expansion: For each retrieved chunk, pulls the corresponding section across
   every version in the document family to guarantee older and newer versions are evaluated.
3. Temporal as-of detection: Identifies point-in-time constraints in queries.
"""

from __future__ import annotations

import re
from typing import Any

from backend.embeddings import cosine_similarity, deserialize_vector, embed_text
from backend.storage import (
    get_all_chunks_with_embeddings,
    get_chunks_by_file_name,
    get_files_for_family,
    search_chunks_fts,
)


def detect_as_of_date(question: str) -> str | None:
    """Detect temporal point-in-time queries (e.g., 'mid-2025', 'March 2024', 'as of 2025-06-01')."""
    q_lower = question.lower()

    # Pattern 1: mid-YYYY or mid YYYY
    mid_match = re.search(r"\bmid[- ](20\d{2})\b", q_lower)
    if mid_match:
        year = mid_match.group(1)
        return f"{year}-07-01"

    # Pattern 2: Month YYYY (e.g., "March 2024", "in March 2024")
    month_names = {
        "january": ("01", "31"),
        "february": ("02", "28"),
        "march": ("03", "31"),
        "april": ("04", "30"),
        "may": ("05", "31"),
        "june": ("06", "30"),
        "july": ("07", "31"),
        "august": ("08", "31"),
        "september": ("09", "30"),
        "october": ("10", "31"),
        "november": ("11", "30"),
        "december": ("12", "31"),
    }
    month_pattern = r"\b(" + "|".join(month_names.keys()) + r")\s+(20\d{2})\b"
    m_match = re.search(month_pattern, q_lower)
    if m_match:
        month_str = m_match.group(1)
        year_str = m_match.group(2)
        mm, dd = month_names[month_str]
        # Leap year check for February
        if mm == "02" and int(year_str) % 4 == 0:
            dd = "29"
        return f"{year_str}-{mm}-{dd}"

    # Pattern 3: Explicit ISO date (e.g., "2025-06-15")
    iso_match = re.search(r"\b(20\d{2}[-/]\d{2}[-/]\d{2})\b", q_lower)
    if iso_match:
        return iso_match.group(1).replace("/", "-")

    return None


def search_hybrid(
    query: str, top_k: int = 12, rrf_k: int = 60
) -> list[tuple[dict[str, Any], float]]:
    """Execute hybrid retrieval combining FTS5 BM25 and ONNX dense vectors via RRF."""
    # 1. Lexical retrieval via SQLite FTS5
    fts_hits = search_chunks_fts(query, limit=top_k * 3)
    rank_fts: dict[str, int] = {hit["chunk_id"]: idx for idx, hit in enumerate(fts_hits)}

    # 2. Dense retrieval via local fastembed vector similarity
    all_chunks = get_all_chunks_with_embeddings()
    dense_scores: list[tuple[dict[str, Any], float]] = []

    if all_chunks:
        query_vec = embed_text(query)
        for chunk in all_chunks:
            blob = chunk.get("embedding")
            if blob:
                vec = deserialize_vector(blob)
                score = cosine_similarity(query_vec, vec)
                dense_scores.append((chunk, score))

        dense_scores.sort(key=lambda x: x[1], reverse=True)

    dense_top = dense_scores[: top_k * 3]
    rank_dense: dict[str, int] = {
        chunk["chunk_id"]: idx for idx, (chunk, _) in enumerate(dense_top)
    }

    # 3. Fuse via Reciprocal Rank Fusion (RRF)
    all_candidate_ids = set(rank_fts.keys()) | set(rank_dense.keys())
    chunk_map: dict[str, dict[str, Any]] = {}
    for h in fts_hits:
        chunk_map[h["chunk_id"]] = h
    for c, _ in dense_top:
        chunk_map[c["chunk_id"]] = c

    scored_chunks: list[tuple[dict[str, Any], float]] = []
    for cid in all_candidate_ids:
        score = 0.0
        if cid in rank_fts:
            score += 1.0 / (rrf_k + rank_fts[cid])
        if cid in rank_dense:
            score += 1.0 / (rrf_k + rank_dense[cid])

        chunk_data = chunk_map[cid]
        scored_chunks.append((chunk_data, score))

    scored_chunks.sort(key=lambda x: x[1], reverse=True)
    return scored_chunks[:top_k]


def _clean_section_title(title: str) -> str:
    """Normalize a section title for semantic matching across document revisions."""
    # Strip leading numbering like '1. ', 'Section 2: ', '2 - '
    cleaned = (
        re.sub(r"^(?:section\s+)?\d+[\.:\-]?\s*", "", title, flags=re.IGNORECASE).strip().lower()
    )
    return cleaned


def expand_siblings(
    hit_chunks: list[dict[str, Any]],
    query: str = "",
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Perform sibling expansion across document version families (Spec 7.3.1).

    Returns:
        dict mapping version_family -> {file_name: [matching_chunk_records]}
    """
    expanded: dict[str, dict[str, list[dict[str, Any]]]] = {}

    for hit in hit_chunks:
        family = hit.get("version_family", "")
        if not family:
            continue

        if family not in expanded:
            expanded[family] = {}

        # Fetch all known files in this version family
        family_files = get_files_for_family(family)
        hit_section_clean = _clean_section_title(hit.get("section_title", ""))

        for f_meta in family_files:
            f_name = f_meta["file_name"]
            if f_name not in expanded[family]:
                expanded[family][f_name] = []

            # Retrieve all chunks for this sibling file
            sibling_chunks = get_chunks_by_file_name(f_name)
            if not sibling_chunks:
                continue

            # Case A: If sibling doc has only 1 chunk (e.g. 1-page PDF), include it
            if len(sibling_chunks) == 1:
                chunk = sibling_chunks[0]
                if not any(c["chunk_id"] == chunk["chunk_id"] for c in expanded[family][f_name]):
                    expanded[family][f_name].append(chunk)
                continue

            # Case B: Match by normalized section title
            matched = False
            for sc in sibling_chunks:
                sc_title_clean = _clean_section_title(sc.get("section_title", ""))
                if sc_title_clean and (
                    sc_title_clean == hit_section_clean
                    or hit_section_clean in sc_title_clean
                    or sc_title_clean in hit_section_clean
                ):
                    if not any(c["chunk_id"] == sc["chunk_id"] for c in expanded[family][f_name]):
                        expanded[family][f_name].append(sc)
                    matched = True

            # Case C: If no section title match, check if query keywords match chunk content
            if not matched and query:
                q_keywords = [
                    w.lower()
                    for w in re.findall(r"\w+", query)
                    if len(w) > 3
                    and w.lower()
                    not in {"what", "when", "does", "many", "days", "much", "there", "about"}
                ]
                for sc in sibling_chunks:
                    content_lower = sc.get("content", "").lower()
                    match_count = sum(1 for kw in q_keywords if kw in content_lower)
                    if match_count >= 2:
                        if not any(
                            c["chunk_id"] == sc["chunk_id"] for c in expanded[family][f_name]
                        ):
                            expanded[family][f_name].append(sc)

    return expanded
