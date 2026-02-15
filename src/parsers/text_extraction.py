"""PDF text extraction using pdfplumber."""

from __future__ import annotations

import pdfplumber


def extract_pdf_text(pdf_path: str) -> str:
    """Extract all text and table content from a PDF using pdfplumber."""
    all_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            page_text = page.extract_text() or ""
            tables = page.extract_tables()

            all_text.append(f"--- Page {i} ---")
            if page_text.strip():
                all_text.append(page_text)

            for t_idx, table in enumerate(tables):
                if table:
                    all_text.append(f"\n[Table {t_idx + 1}]")
                    for row in table:
                        cleaned = [str(cell).strip() if cell else "" for cell in row]
                        all_text.append(" | ".join(cleaned))

    return "\n".join(all_text)
