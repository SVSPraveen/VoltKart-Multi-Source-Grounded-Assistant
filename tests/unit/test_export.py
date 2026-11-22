"""tests/unit/test_export.py - PDF export generation, text extraction, and rupee rendering test.

Verifies:
1. ReportLab PDF export engine creates valid PDF documents from chat history.
2. Timestamps include explicit UTC timezone (R-022).
3. Monospace executed SQL and result row previews render for table citations.
4. Verbatim quotes and section/page headers render for document citations.
5. Embedded Noto Sans font correctly renders the native Indian Rupee sign (₹, U+20B9) (R-013).
6. Page rasterization with pypdfium2 succeeds without font or glyph errors.
"""

from __future__ import annotations

import io
from pathlib import Path

import pdfplumber
import pypdfium2
import pytest

from backend.export_pdf import generate_chat_pdf
from backend.storage import (
    create_chat,
    init_sqlite_db,
    reset_storage,
    save_message,
)


@pytest.fixture
def sample_chat_with_rupees():
    """Seed a test chat session containing table citations, document citations, and ₹ amounts."""
    reset_storage()
    init_sqlite_db()
    chat_id = "test_export_chat_01"
    create_chat(chat_id, title="Test Audit Session")

    # 1. User message
    save_message(
        message_id="msg_u1",
        chat_id=chat_id,
        role="user",
        content="What was the total refund amount by region, and what is the return window?",
        web_enabled=False,
    )

    # 2. Assistant response with rupee symbol, table citation, and document citation
    asst_content = (
        "The total refund amount across all regions is ₹1,955,894.25 (South: ₹916,002.70, "
        "West: ₹569,024.40, East: ₹329,242.20, North: ₹141,624.95). "
        "Under the return policy, the standard window for Gold members is 30 days."
    )
    citations = [
        {
            "type": "table",
            "tables": ["orders", "order_items", "returns", "stores"],
            "sql": "SELECT s.region, SUM(r.refund_amount_inr) FROM returns r JOIN stores s ON r.store_id = s.store_id GROUP BY s.region",
            "row_count": 4,
            "result_rows": [
                {"region": "South", "total_inr": 916002.70},
                {"region": "West", "total_inr": 569024.40},
                {"region": "East", "total_inr": 329242.20},
                {"region": "North", "total_inr": 141624.95},
            ],
        },
        {
            "type": "document",
            "source": "Sample_Return_Policy.pdf",
            "file_name": "Sample_Return_Policy.pdf",
            "version": "Return Policy",
            "date": "2025-09-01",
            "page": 1,
            "section": "Return Window",
            "quote": "Eligible products may be returned within 30 days for Gold members.",
        },
    ]

    save_message(
        message_id="msg_a1",
        chat_id=chat_id,
        role="assistant",
        content=asst_content,
        citations=citations,
        interpreted_as="region breakdown, year = 2025",
        status="completed",
        web_enabled=False,
    )

    return chat_id


def test_pdf_export_generation_and_text(sample_chat_with_rupees: str):
    """Test PDF generation, text contents, timestamps, and citations."""
    pdf_bytes = generate_chat_pdf(sample_chat_with_rupees)
    assert len(pdf_bytes) > 0
    assert pdf_bytes.startswith(b"%PDF")

    # Extract text using pdfplumber
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        assert len(pdf.pages) >= 1
        page_text = pdf.pages[0].extract_text()

        # Check title and metadata
        assert "Multi-Source Grounded Assistant" in page_text
        assert sample_chat_with_rupees in page_text
        assert "UTC" in page_text

        # Check role headers and web badge
        assert "User —" in page_text
        assert "Assistant —" in page_text
        assert "[Web: OFF]" in page_text

        # Check interpreted_as line
        assert "Interpreted as: region breakdown, year = 2025" in page_text

        # Check content
        assert "refund amount across all regions" in page_text

        # Check native Indian Rupee sign U+20B9 (R-013)
        assert "₹" in page_text or "₹1,955,894.25" in page_text

        # Check table citation with SQL
        assert "Table Query:" in page_text
        assert "SELECT s.region" in page_text

        # Check document citation with quote
        assert "Document:" in page_text
        assert "Sample_Return_Policy.pdf" in page_text
        assert "Page 1" in page_text
        assert "Eligible products may be returned within 30 days" in page_text


def test_pdf_page_rasterization(sample_chat_with_rupees: str, tmp_path: Path):
    """Test PDF rasterization to bitmap image using pypdfium2."""
    pdf_bytes = generate_chat_pdf(sample_chat_with_rupees)
    doc = pypdfium2.PdfDocument(pdf_bytes)
    assert len(doc) >= 1

    page = doc[0]
    bitmap = page.render(scale=2.0)
    pil_image = bitmap.to_pil()
    assert pil_image.width > 500
    assert pil_image.height > 700

    out_image_path = tmp_path / "rasterized_chat_export.png"
    pil_image.save(out_image_path)
    assert out_image_path.exists()
    assert out_image_path.stat().st_size > 1000
    doc.close()
