"""backend/documents.py - Structure-aware document parser and section chunker.

Parses PDF (pages + tables via pdfplumber), DOCX (headings + tables via python-docx),
and TXT/MD files. Extracts document dates, normalizes titles into version families,
and chunks text by section while preserving 100% verbatim text for quote verification.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import docx
import pdfplumber

from backend.date_parser import resolve_document_date
from backend.models import DocumentChunk, DocumentMetadata


def extract_table_as_markdown(table_rows: list[list[str | None]]) -> str:
    """Format extracted tabular rows as a markdown table."""
    if not table_rows or not any(table_rows):
        return ""
    # Filter empty rows
    cleaned_rows = [
        [str(cell or "").strip().replace("\n", " ") for cell in row]
        for row in table_rows
        if any(cell for cell in row)
    ]
    if not cleaned_rows:
        return ""

    num_cols = max(len(row) for row in cleaned_rows)
    # Pad rows to uniform width
    padded_rows = [row + [""] * (num_cols - len(row)) for row in cleaned_rows]

    headers = padded_rows[0]
    separator = ["---"] * num_cols
    body = padded_rows[1:]

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(separator) + " |",
    ]
    for row in body:
        lines.append("| " + " | ".join(row) + " |")

    return "\n" + "\n".join(lines) + "\n"


def parse_pdf(file_bytes: bytes) -> tuple[str, list[tuple[int, str]], list[str]]:
    """Parse PDF returning (detected title, list of (1-based page, text), warnings)."""
    pages: list[tuple[int, str]] = []
    warnings: list[str] = []
    detected_title = ""

    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            if not pdf.pages:
                warnings.append("Empty PDF document containing 0 pages")
                return detected_title, pages, warnings

            total_chars = 0
            for page_idx, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text() or ""
                # Extract any tables on the page
                tables = page.extract_tables()
                if tables:
                    for tbl in tables:
                        tbl_md = extract_table_as_markdown(tbl)
                        if tbl_md:
                            page_text += f"\n{tbl_md}\n"

                total_chars += len(page_text.strip())
                pages.append((page_idx, page_text.strip()))

                if page_idx == 1 and page_text:
                    for line in page_text.splitlines():
                        s = line.strip()
                        if s and not re.search(
                            r"\b(date|version|department|effective|owner)\b", s, re.IGNORECASE
                        ):
                            detected_title = s
                            break

            if total_chars < 20:
                warnings.append("Scanned document or missing text layer detected")

    except Exception as exc:
        raise ValueError(f"Failed to read PDF document: {exc}") from exc

    return detected_title, pages, warnings


def parse_docx(file_bytes: bytes) -> tuple[str, list[tuple[str, str]], list[str]]:
    """Parse DOCX returning (detected title, list of (section heading, text), warnings)."""
    sections: list[tuple[str, str]] = []
    warnings: list[str] = []
    detected_title = ""

    try:
        doc = docx.Document(io.BytesIO(file_bytes))
        current_heading = "Header"
        current_paragraphs: list[str] = []

        # Iterate over all document elements in document order
        for elem in doc.element.body:
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag == "p":
                # Paragraph
                p = docx.text.paragraph.Paragraph(elem, doc)
                text = p.text.strip()
                if not text:
                    continue
                style_name = (p.style.name or "").lower() if p.style else ""
                if "title" in style_name and not detected_title:
                    detected_title = text

                if "heading" in style_name or "title" in style_name:
                    # Flush previous section if it has content
                    if current_paragraphs:
                        sections.append((current_heading, "\n".join(current_paragraphs)))
                        current_paragraphs = []
                    current_heading = text
                else:
                    current_paragraphs.append(text)
            elif tag == "tbl":
                # Table
                table = docx.table.Table(elem, doc)
                tbl_rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
                tbl_md = extract_table_as_markdown(tbl_rows)
                if tbl_md:
                    current_paragraphs.append(tbl_md)

        if current_paragraphs:
            sections.append((current_heading, "\n".join(current_paragraphs)))

        if not detected_title and sections:
            detected_title = sections[0][0]

        if not sections:
            warnings.append("DOCX contains no extractable text")

    except Exception as exc:
        raise ValueError(f"Failed to read DOCX document: {exc}") from exc

    return detected_title, sections, warnings


def parse_text(file_bytes: bytes, encoding: str = "utf-8") -> tuple[str, list[tuple[str, str]]]:
    """Parse plain text or markdown by splitting on structural section headings."""
    text = file_bytes.decode(encoding, errors="replace")
    lines = text.splitlines()

    sections: list[tuple[str, str]] = []
    current_heading = "Header"
    current_lines: list[str] = []
    detected_title = ""

    heading_underline_pattern = re.compile(r"^[-=~]{3,}$")
    markdown_heading_pattern = re.compile(r"^#{1,4}\s+(.+)$")
    numbered_heading_pattern = re.compile(r"^\d+\.\s+([A-Za-z\s]+)$")

    idx = 0
    while idx < len(lines):
        line = lines[idx]
        stripped = line.strip()

        # Check for underline heading (e.g., TITLE\n=====)
        if (
            idx + 1 < len(lines)
            and heading_underline_pattern.match(lines[idx + 1].strip())
            and stripped
        ):
            if not detected_title:
                detected_title = stripped
            if current_lines:
                sections.append((current_heading, "\n".join(current_lines).strip()))
                current_lines = []
            current_heading = stripped
            idx += 2
            continue

        # Check for markdown heading (# Section)
        md_match = markdown_heading_pattern.match(stripped)
        if md_match:
            heading_txt = md_match.group(1).strip()
            if not detected_title:
                detected_title = heading_txt
            if current_lines:
                sections.append((current_heading, "\n".join(current_lines).strip()))
                current_lines = []
            current_heading = heading_txt
            idx += 1
            continue

        # Check for numbered section heading (1. Section)
        num_match = numbered_heading_pattern.match(stripped)
        if num_match:
            if current_lines:
                sections.append((current_heading, "\n".join(current_lines).strip()))
                current_lines = []
            current_heading = stripped
            idx += 1
            continue

        current_lines.append(line)
        idx += 1

    if current_lines:
        sections.append((current_heading, "\n".join(current_lines).strip()))

    if not detected_title and lines:
        for line in lines:
            s = line.strip()
            if s and not re.search(r"\b(date|version|effective|owner)\b", s, re.IGNORECASE):
                detected_title = s
                break

    return detected_title, sections


def extract_document_title(first_chunk_text: str, filename: str) -> str:
    """Extract human-readable document title from early content or filename."""
    lines = [line.strip() for line in first_chunk_text.splitlines() if line.strip()]
    for line in lines[:4]:
        # Skip date/version lines
        if re.search(r"\b(date|version|effective|department|job code)\b", line, re.IGNORECASE):
            continue
        # Clean title candidate
        clean = re.sub(r"^#+\s*", "", line).strip()
        if len(clean) >= 4 and len(clean) <= 120:
            return clean

    # Fallback to humanized filename stem
    stem = Path(filename).stem
    stem_clean = re.sub(r"_\d{4}[-_]\d{2}[-_]\d{2}.*$", "", stem)
    return stem_clean.replace("_", " ").title()


def normalize_version_family(title: str, filename: str) -> str:
    """Normalize a title or filename into a canonical version family identifier.

    Heuristic:
    - Lowercase, strip punctuation and extra spaces.
    - Remove date references (e.g. 2024-04-01, 2025, winter 2025).
    - Remove version references (e.g. v1.0, version 2.0, 2026.1).
    - Strip leading brand/company prefixes generically if followed by common doc noun.
    """
    text = f"{title}".lower()

    # Strip ISO dates
    text = re.sub(r"\b\d{4}[-_/]\d{2}[-_/]\d{2}\b", "", text)
    # Strip standalone years or seasonal tags
    text = re.sub(r"\b(winter|summer|spring|fall|autumn)\s*\d{4}\b", "", text)
    text = re.sub(r"\b(19\d{2}|20\d{2})(\.\d+)?\b", "", text)
    # Strip version notations
    text = re.sub(r"\b(v(er(sion)?)?\.?\s*\d+(\.\d+)?)\b", "", text)
    text = re.sub(r"\b(revised|supersedes|effective|draft|final)\b", "", text)
    # Clean non-alphanumeric (keep spaces)
    text = re.sub(r"[^\w\s]", " ", text)
    # Strip generic single leading brand word if multiple words follow
    words = text.split()
    if len(words) >= 3 and words[0] not in {
        "job",
        "return",
        "warranty",
        "store",
        "employee",
        "service",
        "policy",
        "notice",
        "terms",
    }:
        words = words[1:]

    normalized = " ".join(words).strip()
    return normalized or "general_document"


def chunk_document(
    file_bytes: bytes,
    filename: str,
    file_sha256: str,
) -> tuple[DocumentMetadata, list[DocumentChunk]]:
    """Parse document, resolve dates, normalize families, and build verbatim section chunks."""
    ext = Path(filename).suffix.lower()
    chunks: list[DocumentChunk] = []
    warnings: list[str] = []
    page_count: int | None = None
    detected_title = ""

    all_text = ""
    section_entries: list[tuple[str, int | None, str]] = []

    if ext == ".pdf":
        detected_title, pages, pdf_warns = parse_pdf(file_bytes)
        warnings.extend(pdf_warns)
        page_count = len(pages)
        for page_num, p_text in pages:
            all_text += f"\n{p_text}"
            if p_text:
                # Find headings inside page text
                lines = p_text.splitlines()
                cur_heading = f"Page {page_num}"
                cur_lines: list[str] = []
                for line in lines:
                    stripped = line.strip()
                    if re.match(r"^\d+\.\s+[A-Za-z\s]+", stripped):
                        if cur_lines:
                            section_entries.append((cur_heading, page_num, "\n".join(cur_lines)))
                            cur_lines = []
                        cur_heading = stripped
                    else:
                        cur_lines.append(line)
                if cur_lines:
                    section_entries.append((cur_heading, page_num, "\n".join(cur_lines)))
    elif ext == ".docx":
        detected_title, docx_sections, docx_warns = parse_docx(file_bytes)
        warnings.extend(docx_warns)
        for heading, s_text in docx_sections:
            all_text += f"\n{heading}\n{s_text}"
            section_entries.append((heading, None, s_text))
    else:  # .txt, .md
        detected_title, txt_sections = parse_text(file_bytes)
        for heading, s_text in txt_sections:
            all_text += f"\n{heading}\n{s_text}"
            section_entries.append((heading, None, s_text))

    date_res = resolve_document_date(all_text, filename)
    doc_title = detected_title or extract_document_title(all_text[:1000], filename)
    version_family = normalize_version_family(doc_title, filename)

    # Build DocumentChunk objects
    chunk_idx = 0
    for section_title, page_num, content in section_entries:
        cleaned_content = content.strip()
        if not cleaned_content:
            continue
        chunk_id = f"{file_sha256[:12]}_{chunk_idx}"
        token_count = len(cleaned_content.split())
        chunks.append(
            DocumentChunk(
                chunk_id=chunk_id,
                doc_sha256=file_sha256,
                file_name=filename,
                section_title=section_title,
                page_number=page_num,
                content=cleaned_content,
                token_count=token_count,
            )
        )
        chunk_idx += 1

    metadata = DocumentMetadata(
        file_name=filename,
        sha256=file_sha256,
        doc_title=doc_title,
        version_family=version_family,
        doc_date=date_res.doc_date,
        doc_date_source=date_res.source,
        date_disagreement=date_res.date_disagreement,
        page_count=page_count,
        section_count=len(section_entries),
        chunk_count=len(chunks),
        warnings=warnings,
    )

    return metadata, chunks
