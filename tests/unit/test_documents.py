"""tests/unit/test_documents.py - Unit tests for document parsing and chunking (C2, C4).

Verifies PDF page extraction, DOCX heading/table extraction, verbatim text preservation,
and title/version family normalization.
"""

from pathlib import Path

from backend.documents import (
    chunk_document,
    extract_table_as_markdown,
    normalize_version_family,
    parse_text,
)


def test_extract_table_as_markdown():
    """Verify conversion of extracted table cells into formatted markdown tables."""
    raw_table = [
        ["Tier", "Window", "Fee"],
        ["Silver", "10 days", "None"],
        ["Gold", "15 days", "Waived"],
    ]
    md = extract_table_as_markdown(raw_table)
    assert "| Tier | Window | Fee |" in md
    assert "| Silver | 10 days | None |" in md
    assert "| Gold | 15 days | Waived |" in md


def test_parse_text_structural_headings():
    """Verify plain text splitting on markdown and underlined headings."""
    text_content = (
        b"POLICIES AND GUIDELINES\n"
        b"=======================\n"
        b"Document Date: 2025-01-01\n\n"
        b"1. Introduction\n"
        b"All team members should read these guidelines.\n\n"
        b"2. Eligibility\n"
        b"Standard tiers apply across all stores.\n"
    )

    title, sections = parse_text(text_content)
    assert "POLICIES AND GUIDELINES" in title
    assert len(sections) >= 2
    headings = [h for h, _ in sections]
    assert any("Introduction" in h for h in headings)
    assert any("Eligibility" in h for h in headings)


def test_normalize_version_family_heuristics():
    """Verify version family normalization groups revisions together."""
    f1 = normalize_version_family("Corporate Return & Refund Policy", "Policy_2024-04-01.pdf")
    f2 = normalize_version_family("Corporate Return & Refund Policy", "Policy_2025-01-15.docx")
    f3 = normalize_version_family("CORPORATE RETURN & REFUND POLICY", "Policy_2025-09-01.txt")
    assert f1 == f2 == f3
    assert "return refund policy" in f1

    jd1 = normalize_version_family(
        "Job Description: Machine Learning Engineer", "JD_2025-03-10.docx"
    )
    jd2 = normalize_version_family(
        "Job Description: Machine Learning Engineer", "JD_2025-10-20.pdf"
    )
    assert jd1 == jd2
    assert "job description machine learning engineer" in jd1

    w1 = normalize_version_family("Extended Warranty Terms", "Warranty_2024-07-01.txt")
    w2 = normalize_version_family("SuperCare Extended Warranty Terms", "Warranty_2026-02-01.docx")
    assert "warranty terms" in w1
    assert "warranty terms" in w2


def test_verbatim_quote_preservation():
    """Verify chunking preserves 100% verbatim text for exact quote matching (R-019)."""
    raw_text = (
        b"# Refund Timelines\n"
        b"Approved refunds are credited to the original payment method within 7 business days.\n"
    )

    meta, chunks = chunk_document(raw_text, "timelines.md", "dummy_sha_123")
    assert len(chunks) == 1
    expected_quote = (
        "Approved refunds are credited to the original payment method within 7 business days."
    )
    assert expected_quote in chunks[0].content


def test_sample_bundle_documents_extraction():
    """Verify extraction across the sample bundle documents in assignment/."""
    bundle_docs_dir = Path("assignment/VoltKart_Sample_Bundle/documents")
    if not bundle_docs_dir.exists():
        return

    doc_paths = list(bundle_docs_dir.glob("*.*"))
    assert len(doc_paths) == 8

    families: set[str] = set()
    for p in doc_paths:
        meta, chunks = chunk_document(p.read_bytes(), p.name, f"sha_{p.stem}")
        assert meta.doc_date is not None, f"Date missing for {p.name}"
        assert len(chunks) > 0, f"No chunks created for {p.name}"
        families.add(meta.version_family)

    # 8 documents must group into exactly 4 distinct version families
    assert len(families) == 4


def test_numbered_headings_with_punctuation_and_numbers():
    """Verify numbered headings with hyphens, numbers, and punctuation are recognized as sections."""
    text_content = (
        b"POLICY GUIDANCE\n"
        b"===============\n\n"
        b"1. 30-Day Policy\n"
        b"Eligible goods can be returned within 30 days.\n\n"
        b"2. Return Window (All Tiers)\n"
        b"Special rules apply to electronics.\n\n"
        b"3. Restocking Fee: Tier Exceptions\n"
        b"Restocking fee waived for premium tiers.\n"
    )
    title, sections = parse_text(text_content)
    headings = [h for h, _ in sections]
    assert any("30-Day Policy" in h for h in headings)
    assert any("Return Window (All Tiers)" in h for h in headings)
    assert any("Restocking Fee: Tier Exceptions" in h for h in headings)


def test_deeply_nested_markdown_headings():
    """Verify markdown headings at levels h1 through h6 are recognized."""
    text_content = (
        b"# Level 1\nContent 1\n\n"
        b"### Level 3\nContent 3\n\n"
        b"##### Level 5 Sub-clause\nDeep content\n"
    )
    title, sections = parse_text(text_content)
    headings = [h for h, _ in sections]
    assert any("Level 1" in h for h in headings)
    assert any("Level 3" in h for h in headings)
    assert any("Level 5 Sub-clause" in h for h in headings)


def test_adv17_warranty_pricing_domain_guard():
    """Verify ADV-17 fix: general cost questions (lease costs) do not extract warranty pricing."""
    from backend.doc_agent import _extract_claim_pattern

    warranty_chunk = {
        "file_name": "Sample_Warranty_Terms.txt",
        "doc_date": "2025-01-01",
        "version_family": "warranty_terms",
        "section_title": "Pricing & Coverage",
        "page_number": 1,
        "content": (
            "1-year plan: 10% of product price\n"
            "2-year plan: 15% of product price\n"
            "A maximum of 2 claims per product per year is allowed."
        ),
    }

    # Query without warranty domain tokens must NOT match warranty pricing
    claim, _ = _extract_claim_pattern(
        "What is the company profit margin and lease costs?", warranty_chunk
    )
    assert claim is None

    # Query with warranty domain token MUST match warranty pricing
    claim_w, _ = _extract_claim_pattern("What is the cost of the warranty plan?", warranty_chunk)
    assert claim_w is not None
    assert claim_w.states_fact is True
    assert "10%" in claim_w.value


def test_adv18_job_description_role_guard():
    """Verify ADV-18 fix: non-matching roles (e.g. CEO) do not match ML Engineer JD."""
    from backend.doc_agent import _chunk_matches_query_role, _extract_claim_pattern

    jd_chunk = {
        "file_name": "JD_ML_Engineer_2025.docx",
        "doc_date": "2025-03-10",
        "version_family": "job_description",
        "section_title": "Details",
        "page_number": 1,
        "content": (
            "Job Description: Machine Learning Engineer\n"
            "Department: Data Science\n"
            "Location: Bengaluru (on-site)\n"
            "Compensation: INR 12 to 18 LPA\n"
            "Reports to: Ananya Rao, Head of Data Science"
        ),
    }

    # Query asking for CEO must NOT match ML Engineer JD
    assert not _chunk_matches_query_role("what is the ceo compensation?", jd_chunk["content"])
    assert not _chunk_matches_query_role("who does the ceo report to?", jd_chunk["content"])

    claim_ceo_comp, _ = _extract_claim_pattern("What is the CEO compensation?", jd_chunk)
    assert claim_ceo_comp is None

    claim_ceo_rep, _ = _extract_claim_pattern("Who does the CEO report to?", jd_chunk)
    assert claim_ceo_rep is None

    # Query asking for Machine Learning Engineer MUST match
    assert _chunk_matches_query_role(
        "what is the location and salary for the machine learning engineer role?",
        jd_chunk["content"],
    )
    claim_mle_comp, _ = _extract_claim_pattern(
        "What is the salary for the Machine Learning Engineer role?", jd_chunk
    )
    assert claim_mle_comp is not None
    assert claim_mle_comp.states_fact is True
    assert "12 to 18 LPA" in claim_mle_comp.value
