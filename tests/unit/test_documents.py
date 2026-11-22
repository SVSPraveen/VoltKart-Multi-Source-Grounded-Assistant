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
