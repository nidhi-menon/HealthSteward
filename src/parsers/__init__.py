"""AVS PDF parser module.

Parses after-visit summary PDFs into structured medical data using
a section-routing architecture: deterministic parsers where possible,
focused LLM calls (via local Ollama) only for unstructured sections.

No data leaves the machine.
"""

from src.parsers.avs_parser import SectionRouter, postprocess_safety
from src.parsers.text_extraction import extract_pdf_text


def parse_avs_pdf(pdf_path: str, model: str | None = None) -> dict:
    """Parse an after-visit summary PDF into structured medical data.

    Args:
        pdf_path: Path to the PDF file.
        model: Ollama model to use. Defaults to config setting.

    Returns:
        Dict with keys: patient, provider, vitals, diagnoses,
        medication_changes, lab_orders, referrals, follow_up_recommended,
        upcoming_appointments, notes.

    Raises:
        FileNotFoundError: If the PDF file doesn't exist.
        RuntimeError: If PDF has no extractable text or Ollama is unavailable.
    """
    if model is None:
        from src.config import get_settings
        model = get_settings().avs_parser_model

    raw_text = extract_pdf_text(pdf_path)

    if not raw_text.strip():
        raise RuntimeError(
            "No text extracted from PDF. This may be a scanned/image PDF."
        )

    router = SectionRouter(raw_text, model)
    return router.process()
