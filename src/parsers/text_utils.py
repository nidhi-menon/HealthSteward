"""Pure-text utility functions for AVS parsing.

Deterministic extraction of patient name, medication lists,
medication changes, and instruction notes from raw PDF text.
"""

from __future__ import annotations

import re


def _extract_patient_name(raw_text: str) -> str | None:
    """Extract patient name from the AVS header deterministically."""
    m = re.search(r"AFTER VISIT SUMMARY\s*\n(.+)", raw_text)
    if not m:
        return None
    line = m.group(1).strip()
    # Remove CEID suffix if present (e.g. "FirstName LastName CEID: SUT-...")
    line = re.sub(r"\s*CEID:.*", "", line).strip()
    if not line or line[0].isdigit():
        return None
    return line


def parse_med_list(raw_text: str) -> dict[str, dict]:
    """Parse 'Your Medication List' section into a dict keyed by lowercase med name.

    Extracts strength, instructions, brand, and for_diagnoses for each entry
    by parsing the two-column layout that pdfplumber produces.
    """
    start = raw_text.lower().find("your medication list")
    if start == -1:
        return {}
    section = raw_text[start:]
    for end_marker in ["Help us to better help you", "Help us to better"]:
        idx = section.find(end_marker)
        if idx != -1:
            section = section[:idx]

    lines = section.split("\n")

    # --- Pre-process: rejoin lines split by two-column PDF layout ---
    form_words = {"Gel", "Soln", "Shampoo", "Lotion", "Cream", "Tab", "Cap",
                  "Capsule", "Oint", "Ointment", "Liquid", "Susp", "Suspension",
                  "Drops", "Spray", "Patch", "Inhaler"}
    form_words_lower = {w.lower() for w in form_words}
    pct_re = re.compile(r"\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?)?\s*%")

    merged: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        first_word = nxt.split()[0] if nxt.split() else ""
        remainder = nxt.split(None, 1)[1] if len(nxt.split()) > 1 else ""

        # (a) Rejoin split form words: next line starts with a known form word
        #     and current line has a percentage strength.
        if first_word.rstrip(".,:;").lower() in form_words_lower and pct_re.search(line):
            def _insert_form(m: re.Match) -> str:
                prefix = m.group(0)
                return f"{prefix} {first_word}"
            merged_line = re.sub(r"\d+(?:\.\d+)?%(?:\s+Topical)?", _insert_form, line, count=1)
            if remainder:
                merged_line = merged_line + " " + remainder
            merged.append(merged_line)
            i += 2
            continue

        # (b) Rejoin split "Commonly known as:" lines: brand name on next line
        if line.strip().lower() == "commonly known as:" and nxt and nxt[0].isupper():
            merged.append(line.rstrip() + " " + nxt)
            i += 2
            continue

        merged.append(line)
        i += 1
    lines = merged

    # Known dosage form words (after strength number)
    forms = (
        r"(?:Topical\s+)?(?:Tab|Soln|Gel|Shampoo|Lotion|Cream|Cap|Capsule"
        r"|Oint|Ointment|Liquid|Susp|Suspension|Drops|Spray|Patch|Inhaler)"
    )
    strength_re = re.compile(
        r"^(.+?)\s+"
        r"("
        r"\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?)?\s*%\s+" + forms +
        r"|\d+(?:\.\d+)?(?:mcg|mg)\s+\S+"
        r"|PO"
        r"|Lancets"
        r")"
        r"\s*(.*)",
        re.IGNORECASE,
    )

    entries: dict[str, dict] = {}
    current_name: str | None = None
    skip_prefixes = ("your medication list", "as of ", "suggestion", "always use")

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        lower = stripped.lower()

        if any(lower.startswith(p) for p in skip_prefixes):
            continue

        # "Commonly known as:" — may have instruction continuation after brand
        if lower.startswith("commonly known as:"):
            if current_name and current_name in entries:
                after_colon = stripped.split(":", 1)[1].strip()
                parts = after_colon.split(None, 1)
                if parts:
                    entries[current_name]["brand"] = parts[0]
                if len(parts) > 1:
                    cont = parts[1].strip()
                    if entries[current_name].get("instructions"):
                        entries[current_name]["instructions"] += " " + cont
                    else:
                        entries[current_name]["instructions"] = cont
            continue

        if lower.startswith("generic drug:"):
            continue

        # "For diagnoses:"
        if lower.startswith("for diagnoses:"):
            if current_name and current_name in entries:
                dx_text = stripped.split(":", 1)[1].strip()
                entries[current_name].setdefault("for_diagnoses", [])
                entries[current_name]["for_diagnoses"].extend(
                    [d.strip().rstrip(",") for d in dx_text.split(",") if d.strip()]
                )
            continue

        # Continuation of for_diagnoses (standalone condition name on next line)
        if (
            current_name
            and current_name in entries
            and entries[current_name].get("for_diagnoses")
            and not strength_re.match(stripped)
            and not re.match(r"^[A-Z]{2,}\s", stripped)
        ):
            if len(stripped.split()) <= 6 and not any(c.isdigit() for c in stripped):
                entries[current_name]["for_diagnoses"].extend(
                    [d.strip().rstrip(",") for d in stripped.split(",") if d.strip()]
                )
                continue

        # Try matching as a new medication entry
        m = strength_re.match(stripped)
        if m:
            name = m.group(1).strip()
            strength = m.group(2).strip()
            instructions = m.group(3).strip() if m.group(3) else None
            current_name = name.lower()
            entries[current_name] = {
                "name": name,
                "strength": strength,
                "instructions": instructions or None,
            }
            continue

        # Instruction continuation for current med
        if current_name and current_name in entries:
            if entries[current_name].get("instructions"):
                entries[current_name]["instructions"] += " " + stripped
            else:
                entries[current_name]["instructions"] = stripped

    return entries


def parse_med_changes_section(raw_text: str) -> list[dict]:
    """Parse 'Today's medication changes' section deterministically.

    Splits the section by START/STOP/CHANGE headings and extracts each
    medication entry with its action.  Entries whose description contains
    "continue taking" are skipped (administrative, not a real change).

    Returns a list of {"name": ..., "action": ...} dicts.
    """
    start_idx = raw_text.lower().find("today's medication changes")
    if start_idx == -1:
        return []
    section = raw_text[start_idx:]

    for marker in ["Accurate as of", "Pick up these", "Today's Visit",
                    "What's Next", "Your Medication List"]:
        idx = section.find(marker)
        if idx != -1:
            section = section[:idx]

    # Split by action headings (CHANGE how you take: / STOP taking: / START taking:)
    action_re = re.compile(
        r"(CHANGE\s+how you take:|STOP\s+taking:|START\s+taking:)",
        re.IGNORECASE,
    )
    parts = action_re.split(section)

    results: list[dict] = []
    for i in range(1, len(parts), 2):
        heading = parts[i].strip().lower()
        if i + 1 >= len(parts):
            break
        content = parts[i + 1].strip()

        if "change" in heading:
            action = "changed"
        elif "stop" in heading:
            action = "stop"
        else:
            action = "start"

        # Parse medication entries from the content block.
        entries_in_block: list[dict] = []
        current_entry: dict | None = None
        prev_had_desc = False

        for line in content.split("\n"):
            s = line.strip()
            if not s:
                continue
            if "\u2014" in s:                          # em-dash variant
                s = s.replace("\u2014", " — ")
            if " — " in s:
                name, desc = s.split(" — ", 1)
                current_entry = {"name": name.strip(), "desc": desc}
                entries_in_block.append(current_entry)
                prev_had_desc = True
            elif current_entry is None:
                current_entry = {"name": s, "desc": ""}
                entries_in_block.append(current_entry)
                prev_had_desc = False
            elif prev_had_desc:
                current_entry["desc"] += " " + s
            else:
                current_entry = {"name": s, "desc": ""}
                entries_in_block.append(current_entry)
                prev_had_desc = False

        for entry in entries_in_block:
            if "continue taking" in entry["desc"].lower():
                continue
            results.append({"name": entry["name"], "action": entry.get("action", action)})

    return results


def _note_words(text: str) -> set[str]:
    """Extract a set of normalised words for overlap comparison."""
    return {w.strip('.,;:()!?\"\'-') for w in text.lower().split()} - {""}


def _extract_instruction_notes(raw_text: str, data: dict) -> list[str]:
    """Parse notes from the 'Instructions from [provider]' section of raw PDF text.

    Used to supplement LLM-extracted notes with deterministic extraction.
    """
    m = re.search(r'Instructions\s*\nfrom\s+.+', raw_text)
    if not m:
        return []

    start = m.end()

    # Find end of instructions — first known section boundary after the header
    end = len(raw_text)
    for marker in ("Tests ordered:", "New orders ordered",
                    "Today's medication changes", "Today's Visit",
                    "What's Next", "Your Medication List", "\n[Table"):
        idx = raw_text.find(marker, start)
        if 0 < idx < end:
            end = idx

    lines = raw_text[start:end].strip().splitlines()

    # Rejoin continuation lines
    rejoined: list[str] = []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if rejoined and (
            s[0].islower()
            or re.match(r'^\d+\.\s', s)
            or rejoined[-1].rstrip().endswith(',')
        ):
            rejoined[-1] += ' ' + s
        else:
            rejoined.append(s)

    # Merge routine blocks: a line ending with ":" followed by short items
    merged: list[str] = []
    i = 0
    while i < len(rejoined):
        line = rejoined[i]
        if line.rstrip().endswith(":") and i + 1 < len(rejoined):
            items: list[str] = []
            j = i + 1
            while j < len(rejoined):
                candidate = rejoined[j]
                if len(candidate) > 60 or candidate.rstrip().endswith(":"):
                    break
                items.append(candidate)
                j += 1
            if items:
                numbered = [f"{k}. {item}" for k, item in enumerate(items, 1)]
                merged.append(line + " " + " ".join(numbered))
                i = j
                continue
        merged.append(line)
        i += 1

    # Filter out greetings, closings, and items already captured in follow_up
    skip_re = re.compile(
        r'^(nice to see|here is a summary|take care|my schedule|please return in)',
        re.IGNORECASE,
    )
    follow_ups = {
        f["description"].lower()
        for f in (data.get("follow_up_recommended") or [])
        if f.get("description")
    }

    notes: list[str] = []
    for line in merged:
        if skip_re.match(line):
            continue
        if line.lower() in follow_ups:
            continue
        if len(line) < 10:
            continue
        notes.append(line)

    return notes
