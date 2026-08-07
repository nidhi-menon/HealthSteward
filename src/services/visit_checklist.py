"""Deterministic "what to bring" checklist for an upcoming visit (issue #110).

Rules, not an LLM. The things people forget before an appointment — insurance
card, referral paperwork, the imaging disc, the pharmacy address — are the same
things every time, so a rules table gets this right more cheaply and more
predictably than a prompt would, and it costs nothing to run.

Everything here is a pure function over data the caller has already loaded. No
DB access, no I/O, no clock. That keeps the rules directly unit-testable and
means the endpoint stays a thin query-and-render layer.

Known limitation: there is no structured visit-type field on `Appointment`, so
visit-shape rules key off free-text keyword matching on `purpose`, which will
miss phrasings it doesn't know ("come back in 3mo to recheck the thyroid" does
not read as a follow-up). Tracked in issue #144.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChecklistItem:
    """One thing to bring or do before the visit.

    `why` is not decoration: a checklist that explains itself gets followed, and
    it lets someone judge whether a rule actually applies to them.
    `sources` names the rules that produced the item, so a surprising entry can
    be traced back rather than taken on faith.
    """

    id: str
    label: str
    why: str
    category: str  # paperwork | medications | records | questions | logistics
    sources: tuple[str, ...] = ()


# ── Rule inputs ──────────────────────────────────────────────────────────────

# Specialty -> extra items. Matched as a case-insensitive substring of
# `Doctor.specialty`, since that field is free text ("Interventional
# Cardiology" should still match "cardiolog").
SPECIALTY_RULES: dict[str, tuple[ChecklistItem, ...]] = {
    "cardiolog": (
        ChecklistItem(
            id="home_bp_readings",
            label="Your home blood-pressure readings",
            why="Cardiology visits usually open with what your numbers look like outside the clinic.",
            category="records",
        ),
    ),
    "endocrin": (
        ChecklistItem(
            id="glucose_log",
            label="Your recent blood-sugar readings",
            why="Dose adjustments are made off your day-to-day numbers, not the one reading taken today.",
            category="records",
        ),
    ),
    "radiolog": (
        ChecklistItem(
            id="prior_imaging",
            label="Prior imaging (disc, film, or the report)",
            why="Comparing against your earlier scan is often the whole point of the visit.",
            category="records",
        ),
    ),
    "orthoped": (
        ChecklistItem(
            id="prior_imaging",
            label="Prior imaging (disc, film, or the report)",
            why="Comparing against your earlier scan is often the whole point of the visit.",
            category="records",
        ),
    ),
    "ophthalmolog": (
        ChecklistItem(
            id="eyewear_and_sunglasses",
            label="Your glasses or contacts, plus sunglasses",
            why="Your eyes may be dilated, which makes driving home in bright light uncomfortable.",
            category="logistics",
        ),
    ),
    "optometr": (
        ChecklistItem(
            id="eyewear_and_sunglasses",
            label="Your glasses or contacts, plus sunglasses",
            why="Your eyes may be dilated, which makes driving home in bright light uncomfortable.",
            category="logistics",
        ),
    ),
    "dermatolog": (
        ChecklistItem(
            id="skin_change_notes",
            label="When you first noticed each skin change",
            why="Timing matters more than appearance for deciding what needs a biopsy.",
            category="records",
        ),
    ),
    "allerg": (
        ChecklistItem(
            id="reaction_history",
            label="What happened during past reactions, and when",
            why="Allergy workups are built from the reaction history, not just the list of triggers.",
            category="records",
        ),
    ),
    "physical therapy": (
        ChecklistItem(
            id="movement_clothing",
            label="Clothes and shoes you can move in",
            why="You will be asked to demonstrate movement, not just describe it.",
            category="logistics",
        ),
    ),
}

# Keyword -> extra items, matched against a lowercased `Appointment.purpose`.
# Keys are matched as substrings, so "follow" catches "follow-up" and "follow up".
PURPOSE_RULES: tuple[tuple[tuple[str, ...], ChecklistItem], ...] = (
    (
        ("referral", "referred"),
        ChecklistItem(
            id="referral_paperwork",
            label="Your referral paperwork",
            why="Specialist offices often can't bill the visit without it.",
            category="paperwork",
        ),
    ),
    (
        ("follow", "recheck", "re-check"),
        ChecklistItem(
            id="symptom_changes",
            label="Notes on what's changed since your last visit",
            why="A follow-up is mostly about the delta, which is easy to forget in the room.",
            category="questions",
        ),
    ),
    (
        ("mri", "ct scan", "x-ray", "xray", "ultrasound", "imaging", "scan"),
        ChecklistItem(
            id="prior_imaging",
            label="Prior imaging (disc, film, or the report)",
            why="Comparing against your earlier scan is often the whole point of the visit.",
            category="records",
        ),
    ),
    (
        ("mri", "ct scan", "x-ray", "xray", "imaging", "scan"),
        ChecklistItem(
            id="leave_metal_at_home",
            label="Leave jewellery and metal at home",
            why="You'll be asked to remove it anyway, and it's one less thing to lose.",
            category="logistics",
        ),
    ),
    (
        ("lab", "blood work", "bloodwork", "blood draw", "fasting", "panel"),
        ChecklistItem(
            id="fasting_instructions",
            label="Check whether you need to fast, and for how long",
            why="A missed fasting window usually means coming back another day.",
            category="logistics",
        ),
    ),
    (
        ("surgery", "surgical", "pre-op", "preop", "procedure", "biopsy"),
        ChecklistItem(
            id="ride_home",
            label="Arrange a ride home",
            why="Sedation, even light sedation, usually rules out driving yourself.",
            category="logistics",
        ),
    ),
    (
        ("annual", "physical", "wellness", "check-up", "checkup"),
        ChecklistItem(
            id="vaccination_records",
            label="Your vaccination records",
            why="Annual visits are when gaps get caught up, if the record is on hand.",
            category="records",
        ),
    ),
)

FIRST_VISIT_ITEMS: tuple[ChecklistItem, ...] = (
    ChecklistItem(
        id="photo_id_and_insurance",
        label="Photo ID and your insurance card",
        why="A new office has nothing on file, so check-in will ask for both.",
        category="paperwork",
    ),
    ChecklistItem(
        id="pharmacy_details",
        label="Your pharmacy's name and address",
        why="Anything prescribed today gets sent there, and it's asked for at the desk.",
        category="logistics",
    ),
    ChecklistItem(
        id="past_medical_history",
        label="Dates of past surgeries and hospital stays",
        why="New-patient forms ask for these, and they're hard to recall on the spot.",
        category="records",
    ),
)


def build_checklist(
    *,
    specialty: str | None,
    purpose: str | None,
    is_first_visit_with_doctor: bool,
    has_medications: bool,
    has_allergies: bool,
    has_prep_questions: bool,
    open_referral_count: int,
    open_lab_order_count: int,
) -> list[ChecklistItem]:
    """Assemble the checklist for one appointment.

    Deterministic: same inputs, same list, same order. Items are deduplicated by
    `id`, keeping the first occurrence and merging the sources that produced it,
    so a rule firing twice reads as one item with two reasons to be there.
    """
    collected: list[ChecklistItem] = []

    # Baseline — true of essentially every visit.
    if has_medications:
        collected.append(_with_source(_MEDICATION_LIST, "baseline"))
    if has_allergies:
        collected.append(_with_source(_ALLERGY_LIST, "baseline"))
    if has_prep_questions:
        collected.append(_with_source(_PREP_QUESTIONS, "baseline"))

    if is_first_visit_with_doctor:
        for item in FIRST_VISIT_ITEMS:
            collected.append(_with_source(item, "first_visit"))

    if specialty:
        specialty_lower = specialty.lower()
        for keyword, items in SPECIALTY_RULES.items():
            if keyword in specialty_lower:
                for item in items:
                    collected.append(_with_source(item, f"specialty:{keyword}"))

    if purpose:
        purpose_lower = purpose.lower()
        for keywords, item in PURPOSE_RULES:
            matched = next((k for k in keywords if k in purpose_lower), None)
            if matched:
                collected.append(_with_source(item, f"purpose:{matched}"))

    # Outstanding paperwork the profile already knows about. These are the most
    # concrete items on the list precisely because they aren't guesses.
    if open_referral_count:
        collected.append(_with_source(
            ChecklistItem(
                id="referral_paperwork",
                label="Your referral paperwork",
                why=(
                    f"You have {open_referral_count} referral"
                    f"{'s' if open_referral_count != 1 else ''} still open on this profile."
                ),
                category="paperwork",
            ),
            "open_referral",
        ))
    if open_lab_order_count:
        collected.append(_with_source(
            ChecklistItem(
                id="lab_order_slip",
                label="Your lab order slip",
                why=(
                    f"You have {open_lab_order_count} lab order"
                    f"{'s' if open_lab_order_count != 1 else ''} still outstanding."
                ),
                category="paperwork",
            ),
            "open_lab_order",
        ))

    return _dedupe(collected)


_MEDICATION_LIST = ChecklistItem(
    id="medication_list",
    label="Your current medication list",
    why="We can print this from your profile — bring it so doses get checked against what you actually take.",
    category="medications",
)

_ALLERGY_LIST = ChecklistItem(
    id="allergy_list",
    label="Your allergy list",
    why="Worth repeating out loud even when it's already in their chart.",
    category="medications",
)

_PREP_QUESTIONS = ChecklistItem(
    id="prep_questions",
    label="The questions you prepared for this visit",
    why="Questions asked in the room, not remembered in the car afterwards.",
    category="questions",
)


def _with_source(item: ChecklistItem, source: str) -> ChecklistItem:
    return ChecklistItem(
        id=item.id, label=item.label, why=item.why,
        category=item.category, sources=(source,),
    )


def _dedupe(items: list[ChecklistItem]) -> list[ChecklistItem]:
    """First occurrence wins; later duplicates only contribute their source."""
    by_id: dict[str, ChecklistItem] = {}
    order: list[str] = []
    for item in items:
        if item.id in by_id:
            existing = by_id[item.id]
            merged = tuple(dict.fromkeys(existing.sources + item.sources))
            by_id[item.id] = ChecklistItem(
                id=existing.id, label=existing.label, why=existing.why,
                category=existing.category, sources=merged,
            )
        else:
            by_id[item.id] = item
            order.append(item.id)
    return [by_id[item_id] for item_id in order]
