"""Medical Visit PDF Parser — Section Router.

Extracts structured medical information from after-visit summary PDFs
using a section-routing approach: deterministic parsers where possible,
focused LLM calls (via local Ollama) only for unstructured sections.

No data leaves your machine.
"""

from __future__ import annotations

from loguru import logger

from src.parsers.text_utils import _extract_instruction_notes, _note_words
from src.parsers.agent.ollama_chat import direct_chat
from src.parsers.agent.tools import (
    _extract_header_info,
    extract_follow_ups,
    extract_appointments,
    extract_diagnoses,
    get_medication_changes,
)
from src.parsers.agent.section_splitter import SectionSplitter
from src.parsers.agent import prompts


def postprocess_safety(data: dict) -> dict:
    """Minimal structural safety checks.

    Ensures types are correct and no None values in required fields.
    """
    # Notes must be strings
    notes = data.get("notes") or []
    data["notes"] = [
        (n.get("text") if isinstance(n, dict) else n)
        for n in notes
        if (n.get("text") if isinstance(n, dict) else n)
    ]

    # Diagnoses must have condition
    data["diagnoses"] = [
        d for d in (data.get("diagnoses") or [])
        if d.get("condition")
    ]

    # Medication changes must have name and action
    data["medication_changes"] = [
        m for m in (data.get("medication_changes") or [])
        if m.get("name") and m.get("action")
    ]

    # Ensure all top-level keys exist
    for key in ("patient", "provider", "vitals"):
        data.setdefault(key, {})
    for key in ("diagnoses", "medication_changes", "lab_orders",
                "referrals", "follow_up_recommended", "upcoming_appointments", "notes"):
        data.setdefault(key, [])

    return data


class SectionRouter:
    """Processes an AVS document section by section.

    Each section uses the best strategy:
    - deterministic: no LLM needed
    - llm: focused prompt with just one section's text
    - hybrid: deterministic first, LLM supplement
    """

    PIPELINE = [
        ("patient_provider", "deterministic"),
        ("medication_changes", "deterministic"),
        ("follow_up", "deterministic"),
        ("upcoming_appointments", "deterministic"),
        ("diagnoses", "deterministic_or_llm"),
        ("vitals", "llm"),
        ("lab_orders", "llm"),
        ("notes", "hybrid"),
        ("referrals", "llm"),
    ]

    def __init__(self, raw_text: str, model: str) -> None:
        self.raw_text = raw_text
        self.model = model
        self.splitter = SectionSplitter(raw_text)
        self.result: dict = {}

    def process(self) -> dict:
        for section_key, strategy in self.PIPELINE:
            logger.debug(f"Section: {section_key} ({strategy})...")
            if strategy == "deterministic":
                self._process_deterministic(section_key)
            elif strategy == "deterministic_or_llm":
                self._process_deterministic_or_llm(section_key)
            elif strategy == "llm":
                self._process_llm(section_key)
            elif strategy == "hybrid":
                self._process_hybrid(section_key)
        return postprocess_safety(self.result)

    def _process_deterministic(self, section_key: str) -> None:
        if section_key == "patient_provider":
            info = _extract_header_info(self.raw_text)
            self.result["patient"] = info["patient"]
            self.result["provider"] = info["provider"]
        elif section_key == "medication_changes":
            self.result["medication_changes"] = get_medication_changes(self.raw_text)
        elif section_key == "follow_up":
            visit_date = (self.result.get("patient") or {}).get("visit_date")
            self.result["follow_up_recommended"] = extract_follow_ups(self.raw_text, visit_date)
        elif section_key == "upcoming_appointments":
            self.result["upcoming_appointments"] = extract_appointments(self.raw_text)

    def _process_deterministic_or_llm(self, section_key: str) -> None:
        """Try deterministic first; fall back to LLM if no deterministic data."""
        if section_key == "diagnoses":
            det_dx = extract_diagnoses(self.raw_text)
            if det_dx is not None:
                self.result["diagnoses"] = det_dx
                logger.debug(f"  -> deterministic ({len(det_dx)} items)")
                return
            logger.debug("  -> no Assessment section, using LLM")
            self._process_llm(section_key)

    def _process_llm(self, section_key: str) -> None:
        config = {
            "vitals": {
                "sections": ["todays_visit", "vitals_section", "physical_exam"],
                "prompt": prompts.VITALS_SYSTEM,
                "output_key": "vitals",
            },
            "diagnoses": {
                "sections": ["todays_visit", "instructions", "assessment", "impression"],
                "prompt": prompts.DIAGNOSES_SYSTEM,
                "output_key": "diagnoses",
            },
            "lab_orders": {
                "sections": ["lab_orders", "tests_ordered"],
                "prompt": prompts.LAB_ORDERS_SYSTEM,
                "output_key": "lab_orders",
            },
            "referrals": {
                "sections": ["instructions", "plan", "impression"],
                "prompt": prompts.REFERRALS_SYSTEM,
                "output_key": "referrals",
            },
        }

        cfg = config.get(section_key)
        if not cfg:
            return

        # Gather section text
        parts = []
        for sec_name in cfg["sections"]:
            text = self.splitter.get(sec_name)
            if text:
                parts.append(f"--- {sec_name} ---\n{text}")

        if not parts:
            self.result[cfg["output_key"]] = [] if cfg["output_key"] != "vitals" else {
                "weight": None, "bmi": None, "blood_pressure": None,
                "heart_rate": None, "temperature": None,
            }
            return

        section_text = "\n\n".join(parts)

        llm_result = direct_chat(cfg["prompt"], section_text, self.model)

        if llm_result:
            output_key = cfg["output_key"]
            if output_key in llm_result:
                self.result[output_key] = llm_result[output_key]
            elif isinstance(llm_result, list):
                self.result[output_key] = llm_result
            else:
                self.result[output_key] = llm_result

            # Fill in actual visit date for lab orders
            if output_key == "lab_orders":
                visit_date = (self.result.get("patient") or {}).get("visit_date")
                if visit_date:
                    for order in self.result["lab_orders"]:
                        if not order.get("ordered_date") or order["ordered_date"] == "visit date":
                            order["ordered_date"] = visit_date
        else:
            self.result[cfg["output_key"]] = [] if cfg["output_key"] != "vitals" else {
                "weight": None, "bmi": None, "blood_pressure": None,
                "heart_rate": None, "temperature": None,
            }

    def _process_hybrid(self, section_key: str) -> None:
        if section_key == "notes":
            # Deterministic extraction first
            det_notes = _extract_instruction_notes(self.raw_text, self.result)

            # LLM supplement
            section_text = self.splitter.get("instructions") or self.splitter.get("plan")
            if section_text:
                llm_result = direct_chat(prompts.NOTES_SYSTEM, section_text, self.model)
                llm_notes = []
                if llm_result:
                    raw_notes = llm_result.get("notes", []) if isinstance(llm_result, dict) else llm_result
                    for n in raw_notes:
                        if isinstance(n, str):
                            llm_notes.append(n)
                        elif isinstance(n, dict):
                            label = n.get("text") or n.get("title") or n.get("condition") or ""
                            items = None
                            for v in n.values():
                                if isinstance(v, list):
                                    items = v
                                    break
                            if items:
                                note_parts = [f"{label}:"] if label else []
                                note_parts.extend(f"- {s}" for s in items if isinstance(s, str))
                                llm_notes.append("\n".join(note_parts))
                            elif label:
                                llm_notes.append(label)

                # Merge: use deterministic as base, add LLM notes not already covered
                if not det_notes:
                    self.result["notes"] = [n for n in llm_notes if isinstance(n, str) and n.strip()]
                else:
                    merged = list(det_notes)
                    for ln in llm_notes:
                        if not isinstance(ln, str) or not ln.strip():
                            continue
                        ln_words = _note_words(ln)
                        if len(ln_words) < 3:
                            continue
                        covered = False
                        for existing in merged:
                            ex_words = _note_words(existing)
                            if not ex_words:
                                continue
                            shorter = min(len(ln_words), len(ex_words))
                            if len(ln_words & ex_words) / shorter > 0.5:
                                covered = True
                                break
                        if not covered:
                            merged.append(ln)
                    self.result["notes"] = merged
            else:
                self.result["notes"] = det_notes
