"""Splits raw AVS text into named sections by known headers."""

from __future__ import annotations

import re

# Known section headers in typical AVS documents, mapped to canonical keys.
# Order matters: earlier patterns are matched first when determining boundaries.
SECTION_HEADERS: list[tuple[str, re.Pattern]] = [
    # --- Sutter Health AVS sections ---
    ("instructions", re.compile(
        r"^Instructions\s*\n\s*from\s+.+", re.MULTILINE
    )),
    ("medication_changes", re.compile(
        r"Today'?s\s+medication\s+changes", re.IGNORECASE
    )),
    ("todays_visit", re.compile(
        r"Today'?s\s+Visit", re.IGNORECASE
    )),
    ("whats_next", re.compile(
        r"What'?s\s+Next", re.IGNORECASE
    )),
    ("medication_list", re.compile(
        r"Your\s+Medication\s+List", re.IGNORECASE
    )),
    ("lab_orders", re.compile(
        r"(?:Tests\s+ordered|New\s+orders\s+ordered|Lab\s+order)", re.IGNORECASE
    )),
    # --- Tebra / clinical note sections ---
    ("hpi", re.compile(r"^HPI$", re.MULTILINE)),
    ("assessment", re.compile(r"^Assessment$", re.MULTILINE)),
    ("plan", re.compile(r"^Plan\b", re.MULTILINE)),
    ("impression", re.compile(r"^Impression\b", re.MULTILINE)),
    ("physical_exam", re.compile(r"^Physical Examination\b", re.MULTILINE)),
    ("vitals_section", re.compile(r"^Vitals\b", re.MULTILINE)),
    ("medications_current", re.compile(r"^Medications\b", re.MULTILINE)),
    ("tests_ordered", re.compile(r"^Tests(?!\s+ordered)\b", re.MULTILINE)),
    ("follow_up_section", re.compile(r"^Follow-up\b", re.MULTILINE)),
]

MAX_SECTION_CHARS = 2000


class SectionSplitter:
    """Splits raw AVS text by known section headers.

    Results are cached after the first call to `get()` or `all_sections()`.
    Each section is truncated to MAX_SECTION_CHARS for context safety.
    """

    def __init__(self, raw_text: str) -> None:
        self._raw = raw_text
        self._cache: dict[str, str] | None = None

    def _split(self) -> dict[str, str]:
        """Find all section boundaries and extract text between them."""
        # Collect (start_pos, key, match_end_pos) for every header found
        hits: list[tuple[int, str, int]] = []
        for key, pattern in SECTION_HEADERS:
            for m in pattern.finditer(self._raw):
                hits.append((m.start(), key, m.end()))

        if not hits:
            return {}

        # Sort by position in the document
        hits.sort(key=lambda h: h[0])

        # Merge adjacent hits with the same key
        merged: list[tuple[int, str, int]] = []
        for start, key, content_start in hits:
            if merged and merged[-1][1] == key:
                merged[-1] = (merged[-1][0], key, content_start)
            else:
                merged.append((start, key, content_start))
        hits = merged

        sections: dict[str, str] = {}
        for idx, (start, key, content_start) in enumerate(hits):
            if idx + 1 < len(hits):
                end = hits[idx + 1][0]
            else:
                end = len(self._raw)
            text = self._raw[content_start:end].strip()
            # Truncate for context safety
            if len(text) > MAX_SECTION_CHARS:
                text = text[:MAX_SECTION_CHARS] + "\n... [truncated]"
            if key not in sections:
                sections[key] = text
        return sections

    def get(self, section_name: str) -> str | None:
        """Return the text of a single section, or None if not found."""
        if self._cache is None:
            self._cache = self._split()
        return self._cache.get(section_name)

    def all_sections(self) -> dict[str, str]:
        """Return all discovered sections."""
        if self._cache is None:
            self._cache = self._split()
        return dict(self._cache)

    def available_sections(self) -> list[str]:
        """Return the names of all sections found in the document."""
        if self._cache is None:
            self._cache = self._split()
        return list(self._cache.keys())
