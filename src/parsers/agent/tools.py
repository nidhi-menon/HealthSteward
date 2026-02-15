"""Deterministic extraction functions for the section router.

Each function takes raw PDF text and returns structured data
using regex and pattern matching — no LLM needed.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from src.parsers.text_utils import (
    _extract_patient_name,
    parse_med_list,
    parse_med_changes_section,
)


def _extract_header_info(raw_text: str) -> dict:
    """Deterministic regex extraction of visit date, provider, facility, phone from AVS header."""
    info: dict = {
        "patient": {"name": None, "visit_date": None},
        "provider": {"name": None, "facility": None, "phone": None},
    }

    # Patient name
    info["patient"]["name"] = _extract_patient_name(raw_text)

    # Try to parse the header line: "MM/DD/YYYY H:MM AM/PM Facility Phone"
    header_line_m = re.search(
        r"(\d{1,2}/\d{1,2}/\d{4})\s+\d{1,2}:\d{2}\s*(?:AM|PM)\s+"  # date + time
        r"(.+?)\s+"                                                   # facility
        r"(\d{3}-\d{3}-\d{4})",                                       # phone
        raw_text[:1000],
    )
    if header_line_m:
        info["patient"]["visit_date"] = header_line_m.group(1)
        info["provider"]["facility"] = header_line_m.group(2).strip()
        info["provider"]["phone"] = header_line_m.group(3)
    else:
        # Visit date fallbacks
        date_m = re.search(
            r"(?:Date|Visit\s+date)[:\s]+(\d{1,2}/\d{1,2}/\d{4}|\w+\s+\d{1,2},?\s+\d{4})",
            raw_text[:1000], re.IGNORECASE,
        )
        if date_m:
            info["patient"]["visit_date"] = date_m.group(1).strip()
        else:
            date_m2 = re.search(
                r"((?:January|February|March|April|May|June|July|August|September|October|November|December)"
                r"\s+\d{1,2},?\s+\d{4})",
                raw_text[:1500],
            )
            if date_m2:
                info["patient"]["visit_date"] = date_m2.group(1).strip()
            else:
                date_m3 = re.search(r"(\d{1,2}/\d{1,2}/\d{4})", raw_text[:1000])
                if date_m3:
                    info["patient"]["visit_date"] = date_m3.group(1).strip()

        # Facility fallback
        fac_m = re.search(
            r"(?:Facility|Location|Clinic)[:\s]+(.+?)(?:\n|$)",
            raw_text[:1500],
        )
        if not fac_m:
            fac_m2 = re.search(r"(Sutter\s+\w+(?:\s+[-\u2013\u2014]\s+\w[\w\s,]+?))\s+\d{3}-", raw_text[:1500])
            if fac_m2:
                info["provider"]["facility"] = fac_m2.group(1).strip()
        else:
            info["provider"]["facility"] = fac_m.group(1).strip()

        # Phone fallback
        phone_m = re.search(r"(\d{3}[-.)]\s*\d{3}[-.)]\s*\d{4})", raw_text[:2000])
        if phone_m:
            info["provider"]["phone"] = phone_m.group(1).strip()

    # Provider — look for "from <Name>, MD" in Instructions header
    prov_m = re.search(
        r"(?:Instructions\s*\nfrom|from)\s+([A-Z][A-Za-z.\s,]+?(?:MD|DO|NP|PA)\b)",
        raw_text[:3000],
    )
    if prov_m:
        info["provider"]["name"] = prov_m.group(1).strip().rstrip(",")

    # --- Tebra / clinical note fallbacks ---

    # Visit date: "Visited on: 2025 Sep 23 15:20"
    if not info["patient"]["visit_date"]:
        tebra_date = re.search(r"Visited on:\s+(\d{4}\s+\w{3}\s+\d{1,2})", raw_text[:1000])
        if tebra_date:
            info["patient"]["visit_date"] = tebra_date.group(1).strip()

    # Patient name: line before "MRN :"
    if not info["patient"]["name"]:
        tebra_name = re.search(r"^(.+?)\s*\n\s*MRN\s*:", raw_text[:500], re.MULTILINE)
        if tebra_name:
            name = tebra_name.group(1).strip()
            if len(name.split()) <= 4 and not any(c.isdigit() for c in name):
                info["patient"]["name"] = name

    # Provider: "Electronically signed by: Name, M.D."
    if not info["provider"]["name"]:
        tebra_prov = re.search(
            r"Electronically signed by:\s+(.+?,\s*M\.D\.)",
            raw_text[:1000],
        )
        if tebra_prov:
            info["provider"]["name"] = tebra_prov.group(1).strip()

    # Facility: address on second line of header
    if not info["provider"]["facility"]:
        tebra_addr = re.search(
            r"^(\d+\s+.+?,\s*\w+,\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?)",
            raw_text[:300], re.MULTILINE,
        )
        if tebra_addr:
            info["provider"]["facility"] = tebra_addr.group(1).strip()

    # Phone: "Phone : 9009009000" or "Phone: XXX-XXX-XXXX"
    if not info["provider"]["phone"]:
        tebra_phone = re.search(r"Phone\s*:\s*(\d{10}|\d{3}[-.)]\s*\d{3}[-.)]\s*\d{4})", raw_text[:1000])
        if tebra_phone:
            phone = tebra_phone.group(1).strip()
            if len(phone) == 10 and phone.isdigit():
                phone = f"{phone[:3]}-{phone[3:6]}-{phone[6:]}"
            info["provider"]["phone"] = phone

    return info


def _parse_visit_date(date_str: str) -> datetime | None:
    """Try to parse a visit date string into a datetime."""
    for fmt in ("%m/%d/%Y", "%B %d, %Y", "%B %d %Y", "%Y-%m-%d", "%Y %b %d"):
        try:
            return datetime.strptime(date_str.strip().rstrip(","), fmt)
        except ValueError:
            continue
    return None


def _add_months(dt: datetime, months: int) -> datetime:
    """Add months to a datetime, handling month/year overflow."""
    month = dt.month + months
    year = dt.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    day = min(dt.day, [31, 29 if year % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return dt.replace(year=year, month=month, day=day)


def extract_follow_ups(raw_text: str, visit_date_str: str | None = None) -> list[dict]:
    """Deterministic extraction of follow-up recommendations from raw text."""
    visit_dt = None
    if visit_date_str:
        visit_dt = _parse_visit_date(visit_date_str)

    follow_up_re = re.compile(
        r"((?:recheck|see\s+me\s+back|please\s+return|follow\s*[-\s]?up)"
        r"\s+in\s+(?:about\s+)?(\d+)\s*(months|month|weeks|week|days|day))",
        re.IGNORECASE,
    )

    results = []
    seen_descriptions: set[str] = set()

    for m in follow_up_re.finditer(raw_text):
        description = m.group(0).strip()
        amount = int(m.group(2))
        unit = m.group(3).lower()

        desc_lower = description.lower().replace("-", " ")
        if desc_lower in seen_descriptions:
            continue
        seen_descriptions.add(desc_lower)

        target_date = None
        if visit_dt:
            if unit.startswith("month"):
                target_dt = _add_months(visit_dt, amount)
            elif unit.startswith("week"):
                target_dt = visit_dt + timedelta(weeks=amount)
            elif unit.startswith("day"):
                target_dt = visit_dt + timedelta(days=amount)
            else:
                target_dt = None
            if target_dt:
                target_date = target_dt.strftime("%Y-%m-%d")

        description = description[0].upper() + description[1:]

        results.append({
            "description": description,
            "timeframe": f"{amount} {unit}",
            "target_date": target_date,
        })

    return results


# Month abbreviation to full name mapping for appointment parsing
_MONTH_ABBR = {
    "JAN": "January", "FEB": "February", "MAR": "March", "APR": "April",
    "MAY": "May", "JUN": "June", "JUL": "July", "AUG": "August",
    "SEP": "September", "OCT": "October", "NOV": "November", "DEC": "December",
}


def extract_appointments(raw_text: str) -> list[dict]:
    """Deterministic extraction of upcoming appointments from raw text."""
    results = []

    month_abbrs = "|".join(_MONTH_ABBR.keys())
    block_re = re.compile(
        rf"^({month_abbrs})\s+(.+?)$",
        re.MULTILINE,
    )

    for m in block_re.finditer(raw_text):
        month_abbr = m.group(1).upper()
        description = m.group(2).strip()
        block_start = m.end()

        remaining = raw_text[block_start:block_start + 500]
        lines = [l.strip() for l in remaining.split("\n") if l.strip()]

        month_full = _MONTH_ABBR.get(month_abbr, "")

        # Absorb continuation lines into description
        desc_parts = [f"{month_abbr} {description}"]
        past_day = False
        for line in lines:
            if re.match(r"^\d{1,2}$", line):
                past_day = True
                continue
            if re.match(r"^\d{4}$", line):
                break
            if re.search(rf"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+{month_full}", line):
                break
            if past_day and len(line.split()) <= 4 and re.search(r"(?:MD|DO|NP|PA)\b", line):
                desc_parts.append(line)
                continue
            if not past_day:
                desc_parts.append(line)
        full_description = " ".join(desc_parts)

        appt: dict = {
            "description": full_description,
            "date": None,
            "time": None,
            "location": None,
            "phone": None,
        }

        # Look for day number
        day = None
        for line in lines[:5]:
            if re.match(r"^\d{1,2}$", line):
                day = int(line)
                break

        # Look for the full date line
        for line in lines[:8]:
            date_m = re.search(
                rf"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+"
                rf"({month_full}\s+\d{{1,2}})\s+"
                rf"(\d{{1,2}}:\d{{2}}\s*(?:AM|PM))",
                line,
            )
            if date_m:
                appt["time"] = date_m.group(2)
                break

        # Look for year
        year = None
        for line in lines[:8]:
            year_m = re.match(r"^(\d{4})\b", line)
            if year_m:
                year = year_m.group(1)
                break

        if day and month_full and year:
            appt["date"] = f"{month_full} {day}, {year}"
        elif day and month_full:
            appt["date"] = f"{month_full} {day}"

        # Look for phone number
        for line in lines[:10]:
            phone_m = re.search(r"(\d{3}-\d{3}-\d{4})", line)
            if phone_m:
                appt["phone"] = phone_m.group(1)
                break

        # Look for location
        street = None
        city_state_zip = None
        for line in lines[:10]:
            arrive_m = re.search(r"\(Arrive by\s+(.+)", line)
            if arrive_m:
                street = arrive_m.group(1).strip()
                continue
            csz_m = re.search(r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+[A-Z]{2}\s+\d{5})", line)
            if csz_m:
                city_state_zip = csz_m.group(1)
                break

        if street and city_state_zip:
            appt["location"] = f"{street}, {city_state_zip}"
        elif city_state_zip:
            appt["location"] = city_state_zip

        if "video visit" in full_description.lower():
            appt["location"] = None

        results.append(appt)

    return results


def extract_diagnoses(raw_text: str) -> list[dict] | None:
    """Deterministic extraction of diagnoses from an Assessment section.

    Returns None if no Assessment section found (caller should use LLM).
    """
    assessment_m = re.search(
        r"^Assessment\s*\n(.+?)(?=^(?:Plan|Tests|Follow-up)\b|\Z)",
        raw_text, re.MULTILINE | re.DOTALL,
    )
    if not assessment_m:
        return None

    assessment_text = assessment_m.group(1)

    diag_re = re.compile(r"(.+?)\s*\(([A-Z]\d[\w.]+)\)")

    results = []
    seen: set[str] = set()
    for m in diag_re.finditer(assessment_text):
        condition = m.group(1).strip()
        icd_code = m.group(2).strip()
        condition = re.sub(r"^\s*-\s*", "", condition)
        condition = re.sub(r"\s*-\s*$", "", condition).strip()
        if icd_code in seen:
            continue
        seen.add(icd_code)
        results.append({"condition": condition, "icd_10": icd_code})

    return results if results else None


def get_medication_changes(raw_text: str) -> list[dict]:
    """Deterministic extraction of medication changes, enriched from medication list."""
    changes = parse_med_changes_section(raw_text)
    med_list = parse_med_list(raw_text)

    header = _extract_header_info(raw_text)
    visit_date = header["patient"].get("visit_date")

    results = []
    for change in changes:
        entry = {
            "name": change["name"],
            "action": change["action"],
            "strength": None,
            "instructions": None,
            "date": visit_date,
        }

        # Enrich from medication list
        clean_name = re.sub(r"\s*\(.*?\)", "", change["name"]).strip().lower()
        ml_entry = med_list.get(clean_name)
        if not ml_entry and " " in clean_name:
            ml_entry = med_list.get(clean_name.split()[0])
        if not ml_entry:
            paren_match = re.search(r"\(([^)]+)\)", change["name"])
            if paren_match:
                ml_entry = med_list.get(paren_match.group(1).strip().lower())

        if ml_entry:
            entry["strength"] = ml_entry.get("strength")
            entry["instructions"] = ml_entry.get("instructions")
            if ml_entry.get("brand"):
                entry["name"] = f"{ml_entry.get('name', change['name'])} ({ml_entry['brand']})"

        results.append(entry)

    return results
