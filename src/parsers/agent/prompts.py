"""System prompts for per-section LLM extraction."""

# Version tags for each prompt below — bump the relevant entry and add an
# entry to docs/notes/PROMPT_CHANGELOG.md whenever a prompt's content
# changes (project-wide prompt-versioning convention, started 2026-07-19).
PROMPT_VERSIONS = {
    "VITALS_SYSTEM": "v1",
    "DIAGNOSES_SYSTEM": "v1",
    "LAB_ORDERS_SYSTEM": "v1",
    "NOTES_SYSTEM": "v1",
    "REFERRALS_SYSTEM": "v1",
}

VITALS_SYSTEM = """\
Extract vitals from this medical visit text. Return ONLY a JSON object:
{"weight": "string or null", "bmi": number or null, "blood_pressure": "string or null", "heart_rate": "string or null", "temperature": "string or null"}
Use null for any vital not mentioned. Return ONLY the JSON."""

DIAGNOSES_SYSTEM = """\
Extract diagnoses from this medical visit text. Return ONLY a JSON array:
[{"condition": "string", "icd_10": "ICD-10-CM code or null"}]
Include ONLY conditions discussed during THIS visit. Each must have a "condition" and "icd_10" field.
Use standard ICD-10-CM codes for well-known conditions (e.g. E06.3 for Hashimoto's, L21.9 for seborrheic dermatitis, L70.0 for acne vulgaris, E28.2 for PCOS).
Return ONLY the JSON array."""

LAB_ORDERS_SYSTEM = """\
Extract lab tests ordered during this visit from the text. Return ONLY a JSON object:
{"lab_orders": [{"test": "test name", "ordered_date": "visit date"}]}
Include any test listed in a "Tests ordered" or "Lab orders" section, even if the name is general (e.g. "Baseline Labs").
Do NOT include scheduled lab appointments (those have dates/times/locations).
If no tests were ordered, return {"lab_orders": []}.
Return ONLY the JSON."""

NOTES_SYSTEM = """\
Extract actionable instructions and recommendations from this text. Return ONLY a JSON object:
{"notes": ["string"]}
Each distinct instruction, recommendation, or piece of advice is a separate note.
Include: medication interaction warnings, lifestyle recommendations, conditional advice,
pill-taking tips, dosage instructions, treatment protocols, skincare routines, product recommendations.
Preserve ordered routines/regimens as a single note with all steps.
Do NOT include greetings, closings, or content that belongs in other fields (med changes, lab orders).
Be thorough — do not summarize or omit details.
Return ONLY the JSON."""

REFERRALS_SYSTEM = """\
Extract referrals to NEW specialists or providers from this text. Return ONLY a JSON object:
{"referrals": [{"specialty": "string", "provider": "string or null", "reason": "string or null"}]}
A referral is when the patient is being sent to a DIFFERENT doctor or specialist they haven't been seeing.
Do NOT include: follow-up visits with the current provider, medication adjustments, or general recommendations.
If no referrals are mentioned, return {"referrals": []}.
Return ONLY the JSON."""
