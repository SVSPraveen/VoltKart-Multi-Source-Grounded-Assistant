"""backend/export_pdf.py - Server-side PDF export engine using ReportLab.

Implements Spec Section 7.7 & ADR-006:
1. Export chat history with UTC timestamps, chat ID, and roles.
2. Embeds Unicode TrueType font (Noto Sans) for native Indian Rupee (₹, U+20B9) rendering (R-013).
3. Formats document citations with verbatim quotes and section/page.
4. Formats table citations with monospace executed SQL and result row previews.
5. Notes web search toggle state per message.
"""

from __future__ import annotations

import html
import io
import time
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus import (
    Image as RLImage,
)

from backend.charts import render_chart_image
from backend.storage import get_chat, get_chat_messages

# Register bundled Noto Sans Unicode fonts for native ₹ rendering
FONTS_DIR = Path(__file__).resolve().parent / "fonts"
REGULAR_FONT_PATH = FONTS_DIR / "NotoSans-Regular.ttf"
BOLD_FONT_PATH = FONTS_DIR / "NotoSans-Bold.ttf"

_FONTS_REGISTERED = False


def ensure_unicode_fonts() -> str:
    """Register Noto Sans TrueType font family with ReportLab.

    Returns the font family name ('NotoSans' if registered, or fallback 'Helvetica').
    """
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return "NotoSans"

    if REGULAR_FONT_PATH.exists():
        pdfmetrics.registerFont(TTFont("NotoSans", str(REGULAR_FONT_PATH)))
        if BOLD_FONT_PATH.exists():
            pdfmetrics.registerFont(TTFont("NotoSans-Bold", str(BOLD_FONT_PATH)))
        else:
            pdfmetrics.registerFont(TTFont("NotoSans-Bold", str(REGULAR_FONT_PATH)))
        _FONTS_REGISTERED = True
        return "NotoSans"

    return "Helvetica"


def _clean_text(text: str) -> str:
    """Escape HTML entities for ReportLab Paragraphs and preserve linebreaks."""
    escaped = html.escape(text)
    return escaped.replace("\n", "<br/>")


def generate_chat_pdf(chat_id: str) -> bytes:
    """Generate a publication-grade PDF audit report for a given chat_id."""
    font_name = ensure_unicode_fonts()
    bold_font = "NotoSans-Bold" if font_name == "NotoSans" else "Helvetica-Bold"

    chat_info = get_chat(chat_id) or {"chat_id": chat_id, "title": "Chat Export"}
    messages = get_chat_messages(chat_id)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    styles = getSampleStyleSheet()

    # Custom styles adhering to DESIGN.md palette and typography
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontName=bold_font,
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#111827"),
    )
    meta_style = ParagraphStyle(
        "DocMeta",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#4B5563"),
    )
    role_user_style = ParagraphStyle(
        "RoleUser",
        parent=styles["Heading3"],
        fontName=bold_font,
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#1F2937"),
    )
    role_asst_style = ParagraphStyle(
        "RoleAsst",
        parent=styles["Heading3"],
        fontName=bold_font,
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#0F766E"),
    )
    body_style = ParagraphStyle(
        "MessageBody",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#111827"),
    )
    interpreted_style = ParagraphStyle(
        "InterpretedAs",
        parent=styles["Italic"],
        fontName=font_name,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#6B7280"),
    )
    sql_style = ParagraphStyle(
        "SQLStyle",
        parent=styles["Code"],
        fontName="Courier",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#1E293B"),
    )
    citation_header_style = ParagraphStyle(
        "CitationHeader",
        parent=styles["Normal"],
        fontName=bold_font,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#374151"),
    )
    citation_text_style = ParagraphStyle(
        "CitationText",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor("#4B5563"),
    )

    story = []

    # Title Banner
    story.append(Paragraph("Multi-Source Grounded Assistant — Chat Export", title_style))
    now_utc = time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime())
    meta_text = (
        f"<b>Chat ID:</b> {chat_id} &nbsp;|&nbsp; "
        f"<b>Title:</b> {_clean_text(chat_info.get('title', 'Chat'))} &nbsp;|&nbsp; "
        f"<b>Exported:</b> {now_utc} (UTC)"
    )
    story.append(Paragraph(meta_text, meta_style))
    story.append(Spacer(1, 15))
    story.append(
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E5E2D9"), spaceAfter=15)
    )

    if not messages:
        story.append(Paragraph("<i>No messages in this chat conversation.</i>", body_style))
    else:
        for _idx, msg in enumerate(messages, 1):
            role = msg.get("role", "user")
            created_at = msg.get("created_at", "")
            web_enabled = bool(msg.get("web_enabled", False))
            content = msg.get("content", "")
            interpreted_as = msg.get("interpreted_as")
            citations = msg.get("citations", [])

            # Role Header with Timestamp
            web_badge = " [Web: ON]" if web_enabled else " [Web: OFF]"
            if role == "user":
                role_label = f"User — {created_at} {web_badge}"
                story.append(Paragraph(role_label, role_user_style))
            else:
                role_label = f"Assistant — {created_at}"
                story.append(Paragraph(role_label, role_asst_style))

            story.append(Spacer(1, 4))

            # Quiet Interpreted As line
            if interpreted_as:
                story.append(
                    Paragraph(
                        f"<i>Interpreted as: {_clean_text(interpreted_as)}</i>", interpreted_style
                    )
                )
                story.append(Spacer(1, 4))

            # Main content
            story.append(Paragraph(_clean_text(content), body_style))
            story.append(Spacer(1, 8))

            # Re-render embedded analytical charts from stored specs (B10, spec 7.7)
            charts = msg.get("charts", [])
            for c_spec in charts:
                try:
                    png_bytes = render_chart_image(c_spec, width=800, height=360)
                    chart_flowable = RLImage(io.BytesIO(png_bytes), width=480, height=216)
                    story.append(KeepTogether([chart_flowable, Spacer(1, 10)]))
                except Exception:
                    pass

            # Render Citations if present
            if citations:
                citation_elements = []
                citation_elements.append(
                    Paragraph("<b>Verified Sources & Evidence:</b>", citation_header_style)
                )
                citation_elements.append(Spacer(1, 4))

                for c_idx, c in enumerate(citations, 1):
                    c_type = c.get("type", "document")
                    if c_type == "table":
                        tbls = ", ".join(c.get("tables", []))
                        sql_stmt = c.get("sql", "").strip()
                        c_text = f"<b>[{c_idx}] Table Query:</b> {tbls} ({c.get('row_count', 0)} rows returned)"
                        citation_elements.append(Paragraph(c_text, citation_text_style))
                        if sql_stmt:
                            citation_elements.append(Spacer(1, 2))
                            # Monospace SQL in subtle box
                            sql_p = Paragraph(_clean_text(sql_stmt), sql_style)
                            sql_box = Table([[sql_p]], colWidths=[520])
                            sql_box.setStyle(
                                TableStyle(
                                    [
                                        (
                                            "BACKGROUND",
                                            (0, 0),
                                            (-1, -1),
                                            colors.HexColor("#F8FAFC"),
                                        ),
                                        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                                    ]
                                )
                            )
                            citation_elements.append(sql_box)

                        # Preview rows table if present
                        rows = c.get("result_rows", [])
                        if rows and isinstance(rows[0], dict):
                            col_keys = list(rows[0].keys())[:5]
                            table_data = [
                                [Paragraph(f"<b>{k}</b>", citation_text_style) for k in col_keys]
                            ]
                            for r in rows[:4]:
                                table_data.append(
                                    [
                                        Paragraph(str(r.get(k, "")), citation_text_style)
                                        for k in col_keys
                                    ]
                                )
                            preview_tbl = Table(
                                table_data, colWidths=[520 / len(col_keys)] * len(col_keys)
                            )
                            preview_tbl.setStyle(
                                TableStyle(
                                    [
                                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
                                        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                                        (
                                            "INNERGRID",
                                            (0, 0),
                                            (-1, -1),
                                            0.5,
                                            colors.HexColor("#E2E8F0"),
                                        ),
                                        ("TOPPADDING", (0, 0), (-1, -1), 2),
                                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                                    ]
                                )
                            )
                            citation_elements.append(Spacer(1, 3))
                            citation_elements.append(preview_tbl)

                    else:
                        # Document citation
                        src = c.get("source") or c.get("file_name", "Document")
                        date = c.get("date", "")
                        sec = c.get("section", "")
                        page = c.get("page")
                        quote = c.get("quote", "").strip()

                        loc_parts = []
                        if page:
                            loc_parts.append(f"Page {page}")
                        if sec:
                            loc_parts.append(f"Section: {sec}")
                        loc_str = f" ({', '.join(loc_parts)})" if loc_parts else ""

                        doc_meta = f"<b>[{c_idx}] Document:</b> {src} &nbsp;[Date: {date}]{loc_str}"
                        citation_elements.append(Paragraph(doc_meta, citation_text_style))
                        if quote:
                            q_text = f'<i>Verbatim Evidence:</i> "{_clean_text(quote)}"'
                            citation_elements.append(Paragraph(q_text, citation_text_style))

                    citation_elements.append(Spacer(1, 4))

                story.append(KeepTogether(citation_elements))

            story.append(Spacer(1, 10))
            story.append(
                HRFlowable(
                    width="100%", thickness=0.5, color=colors.HexColor("#F3F4F6"), spaceAfter=10
                )
            )

    doc.build(story)
    return buffer.getvalue()
