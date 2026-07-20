"""Synthetic eval cases for the visit-prep generation harness (issue #29).

Each case is fabricated data, not real patient history — see the
"synthetic example" convention already used by docs/tdd.html's Walkthrough
tab. Every case is deliberately constructed to exercise a specific check,
not just be "a plausible patient":

- cross_specialty_scope: a medication tagged for an unrelated specialty
  sits on the same profile as the target visit's own medication, so the
  scope checker (issue #29 build-order item #1) has something real to
  catch if the model asks about it.
- groundedness_labs_vitals: lab orders + a vitals trend exist so the
  groundedness entity-match check (item #6) has real entities to look for.
- cold_start: zero past visits, zero medications — exercises the
  fallback/format-validity path with minimal input.
- tool_call_necessity_dosing: two same-specialty medications with a real
  absorption-timing interaction (mirrors docs/tdd.html's Walkthrough
  example) — the "correct" answer benefits from a get_medication_details
  call, so this case's tool_calls are worth checking for.
- retrieval_redundancy: enough past visits with the target doctor that
  Phase 1 (ContextSelector) already selects some of them, so if the model
  calls lookup_past_visits, the harness can check whether Phase 2 just
  re-fetched what Phase 1 already provided.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DoctorFixture:
    key: str  # local reference key, not persisted
    name: str
    specialty: Optional[str] = None
    clinic: Optional[str] = None
    exclude_from_prep_context: bool = False


@dataclass
class ConditionFixture:
    name: str
    icd_10: Optional[str] = None
    status: str = "active"
    severity: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class MedicationFixture:
    name: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    prescribing_doctor_key: Optional[str] = None  # resolved to DoctorFixture.name at build time
    purpose: Optional[str] = None
    side_effects: Optional[str] = None


@dataclass
class PastVisitFixture:
    doctor_key: str
    scheduled_date: str  # ISO datetime
    purpose: Optional[str] = None
    visit_notes: Optional[str] = None
    status: str = "completed"


@dataclass
class LabOrderFixture:
    test_name: str
    ordered_date: Optional[str] = None


@dataclass
class VitalsFixture:
    weight: Optional[str] = None
    bmi: Optional[float] = None
    blood_pressure: Optional[str] = None
    heart_rate: Optional[str] = None
    measured_date: Optional[str] = None


@dataclass
class EvalCase:
    id: str
    description: str
    profile_name: str
    doctors: list[DoctorFixture]
    target_doctor_key: str
    appointment_purpose: str
    appointment_scheduled_date: str  # ISO datetime, must be after all past_visits
    conditions: list[ConditionFixture] = field(default_factory=list)
    medications: list[MedicationFixture] = field(default_factory=list)
    past_visits: list[PastVisitFixture] = field(default_factory=list)
    lab_orders: list[LabOrderFixture] = field(default_factory=list)
    vitals: list[VitalsFixture] = field(default_factory=list)
    # Tool name whose presence in the run's tool_calls is worth reporting on
    # (issue #29's Phase-2 "tool-call necessity" check) — observational, not
    # a hard pass/fail, since a well-behaved agent isn't guaranteed to call
    # a tool just because a case was designed to make one useful.
    expects_tool_call: Optional[str] = None


GENERATION_CASES: list[EvalCase] = [
    EvalCase(
        id="cross_specialty_scope",
        description=(
            "Endocrinology visit; patient also has a dermatology medication "
            "from an unrelated doctor — scope checker should catch a question "
            "about it if the model generates one."
        ),
        profile_name="Eval Patient — Cross Specialty",
        doctors=[
            DoctorFixture(key="target", name="Dr. Elena Vance", specialty="Endocrinology", clinic="Bay Endocrinology"),
            DoctorFixture(key="derm", name="Dr. Rita Fields", specialty="Dermatology", clinic="Clearskin Dermatology"),
        ],
        target_doctor_key="target",
        appointment_purpose="Diabetes follow-up",
        appointment_scheduled_date="2026-08-01T10:00:00",
        conditions=[
            ConditionFixture(name="Type 2 Diabetes Mellitus", icd_10="E11.9", status="active"),
            ConditionFixture(name="Mild Plaque Psoriasis", icd_10="L40.0", status="active"),
        ],
        medications=[
            MedicationFixture(
                name="Metformin", dosage="500mg", frequency="twice daily",
                prescribing_doctor_key="target", purpose="Blood sugar control",
            ),
            MedicationFixture(
                name="Clobetasol Cream", dosage="0.05%", frequency="once daily",
                prescribing_doctor_key="derm", purpose="Psoriasis flare control",
            ),
        ],
    ),
    EvalCase(
        id="groundedness_labs_vitals",
        description=(
            "Endocrinology visit with lab orders and a vitals trend present, "
            "so the groundedness entity-match check has real entities to find."
        ),
        profile_name="Eval Patient — Groundedness",
        doctors=[
            DoctorFixture(key="target", name="Dr. Elena Vance", specialty="Endocrinology", clinic="Bay Endocrinology"),
        ],
        target_doctor_key="target",
        appointment_purpose="Thyroid check",
        appointment_scheduled_date="2026-08-02T10:00:00",
        conditions=[
            ConditionFixture(name="Hashimoto's Thyroiditis", icd_10="E06.3", status="active"),
        ],
        medications=[
            MedicationFixture(
                name="Levothyroxine", dosage="75mcg", frequency="once daily, morning",
                prescribing_doctor_key="target", purpose="Thyroid hormone replacement",
            ),
        ],
        lab_orders=[
            LabOrderFixture(test_name="TSH", ordered_date="2026-07-15"),
        ],
        vitals=[
            VitalsFixture(weight="165 lbs", bmi=26.1, blood_pressure="122/78", measured_date="2026-07-15"),
            VitalsFixture(weight="168 lbs", bmi=26.6, blood_pressure="124/80", measured_date="2026-04-10"),
        ],
    ),
    EvalCase(
        id="cold_start",
        description=(
            "Minimal profile: one condition, no medications, no past visits, "
            "no labs — exercises the fallback/format-validity path."
        ),
        profile_name="Eval Patient — Cold Start",
        doctors=[
            DoctorFixture(key="target", name="Dr. Alex Kim", specialty="Family Medicine", clinic="Riverside Family Practice"),
        ],
        target_doctor_key="target",
        appointment_purpose="Annual physical",
        appointment_scheduled_date="2026-08-03T09:00:00",
        conditions=[
            ConditionFixture(name="Seasonal Allergic Rhinitis", icd_10="J30.2", status="active"),
        ],
    ),
    EvalCase(
        id="tool_call_necessity_dosing",
        description=(
            "Two same-specialty medications with a real absorption-timing "
            "interaction (mirrors docs/tdd.html's Walkthrough example) — "
            "get_medication_details is worth calling to answer this well."
        ),
        profile_name="Eval Patient — Dosing",
        doctors=[
            DoctorFixture(key="target", name="Dr. Elena Vance", specialty="Endocrinology", clinic="Bay Endocrinology"),
        ],
        target_doctor_key="target",
        appointment_purpose="Diabetes and thyroid follow-up — reviewing medication timing",
        appointment_scheduled_date="2026-08-04T10:00:00",
        conditions=[
            ConditionFixture(name="Type 2 Diabetes Mellitus", icd_10="E11.9", status="active"),
            ConditionFixture(name="Hashimoto's Thyroiditis", icd_10="E06.3", status="active"),
        ],
        medications=[
            MedicationFixture(
                name="Metformin", dosage="500mg", frequency="twice daily",
                prescribing_doctor_key="target", purpose="Blood sugar control",
            ),
            MedicationFixture(
                name="Levothyroxine", dosage="75mcg", frequency="once daily, morning",
                prescribing_doctor_key="target", purpose="Thyroid hormone replacement",
            ),
        ],
        expects_tool_call="get_medication_details",
    ),
    EvalCase(
        id="retrieval_redundancy",
        description=(
            "Several past visits with the target doctor, already surfaced by "
            "Phase 1 context selection — if the model calls lookup_past_visits, "
            "check whether it just re-fetched what Phase 1 already provided."
        ),
        profile_name="Eval Patient — Redundancy",
        doctors=[
            DoctorFixture(key="target", name="Dr. Elena Vance", specialty="Endocrinology", clinic="Bay Endocrinology"),
        ],
        target_doctor_key="target",
        appointment_purpose="Reviewing thyroid management history and recent lab trends",
        appointment_scheduled_date="2026-08-05T10:00:00",
        conditions=[
            ConditionFixture(name="Hashimoto's Thyroiditis", icd_10="E06.3", status="active"),
        ],
        medications=[
            MedicationFixture(
                name="Levothyroxine", dosage="75mcg", frequency="once daily, morning",
                prescribing_doctor_key="target", purpose="Thyroid hormone replacement",
            ),
        ],
        past_visits=[
            PastVisitFixture(
                doctor_key="target", scheduled_date="2026-05-01T10:00:00",
                purpose="Thyroid follow-up", visit_notes="TSH trending down, dose unchanged.",
            ),
            PastVisitFixture(
                doctor_key="target", scheduled_date="2026-02-01T10:00:00",
                purpose="Thyroid follow-up", visit_notes="Increased Levothyroxine to 75mcg.",
            ),
            PastVisitFixture(
                doctor_key="target", scheduled_date="2025-11-01T10:00:00",
                purpose="Initial Hashimoto's diagnosis", visit_notes="Started Levothyroxine 50mcg.",
            ),
        ],
        expects_tool_call="lookup_past_visits",
    ),
]
