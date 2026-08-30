"""25 additional synthetic patient cases for the human-vs-LLM-judge review
study (see docs/notes/... review packet work), extending the 5 deliberately
adversarial cases in eval/fixtures.py's GENERATION_CASES.

Those 5 are all engineered to probe a specific known failure mode (scope
leakage, groundedness, cold start, dosing tool-call necessity, retrieval
redundancy) — none represent "an ordinary patient." Reviewing only those 5
would answer "does the system survive known edge cases," not "how does the
system behave on the distribution it will actually see," and a reviewer
could reasonably call the sample cherry-picked. This module is built to
close that gap along three axes: specialty coverage, data-richness range,
and routine-vs-adversarial balance.

Kept as a separate module (not appended to GENERATION_CASES) deliberately —
GENERATION_CASES is consumed by eval/run.py's fixed per-case
expected_min_questions floor (scorers.expected_min_questions) and by
tests/test_eval_harness.py's exact-set assertion against EXPECTED_FLOORS.
Appending here would either need 25 new hand-tuned floors and a test-file
change, or silently break that test. REVIEW_STUDY_CASES is meant for the
judge (eval/judge.py) and the human-review packet, not eval.run's
floor/scope-violation scoring pipeline.

Schema notes for two ideas from the design sketch that don't fit the
current fixture dataclasses, resolved by using what already exists rather
than adding new fields:
- MedicationFixture has no "discontinued" status (unlike ConditionFixture,
  which does). A "recently stopped medication" case is represented instead
  as a past-visit note mentioning the discontinuation, with the medication
  deliberately absent from the current `medications` list — the case
  worth testing is whether the model still asks about it as if current.
- EvalCase/build_case has no per-case date_of_birth (eval/db.py hardcodes
  _DEFAULT_DOB for every case); an age-varying case isn't representable
  without a harness change, so it's out of scope here rather than faked.
"""

from eval.fixtures import (
    ConditionFixture,
    DoctorFixture,
    EvalCase,
    LabOrderFixture,
    MedicationFixture,
    PastVisitFixture,
    VitalsFixture,
)

# ── Tier A: 12 routine (non-adversarial) cases, one per specialty ──────────
# Ordinary patients — nothing engineered to trip a specific check. This is
# the set that characterizes typical behavior, not just worst-case survival.

_TIER_A = [
    EvalCase(
        id="routine_cardiology",
        description="Routine cardiology follow-up for atrial fibrillation on anticoagulation.",
        profile_name="Eval Patient — Cardiology Routine",
        doctors=[DoctorFixture(key="target", name="Dr. Priya Nair", specialty="Cardiology", clinic="Harborview Cardiology")],
        target_doctor_key="target",
        appointment_purpose="Atrial fibrillation follow-up",
        appointment_scheduled_date="2026-09-01T09:00:00",
        conditions=[ConditionFixture(name="Atrial Fibrillation", icd_10="I48.91", status="active")],
        medications=[
            MedicationFixture(name="Apixaban", dosage="5mg", frequency="twice daily", prescribing_doctor_key="target", purpose="Stroke prevention"),
            MedicationFixture(name="Metoprolol", dosage="25mg", frequency="twice daily", prescribing_doctor_key="target", purpose="Rate control"),
        ],
    ),
    EvalCase(
        id="routine_psychiatry",
        description="Routine psychiatry follow-up for major depressive disorder on an SSRI.",
        profile_name="Eval Patient — Psychiatry Routine",
        doctors=[DoctorFixture(key="target", name="Dr. Sam Okafor", specialty="Psychiatry", clinic="Lakeside Behavioral Health")],
        target_doctor_key="target",
        appointment_purpose="Medication follow-up",
        appointment_scheduled_date="2026-09-01T10:00:00",
        conditions=[ConditionFixture(name="Major Depressive Disorder", icd_10="F33.1", status="active")],
        medications=[
            MedicationFixture(name="Sertraline", dosage="100mg", frequency="once daily", prescribing_doctor_key="target", purpose="Depression management"),
        ],
    ),
    EvalCase(
        id="routine_rheumatology",
        description="Routine rheumatology follow-up for rheumatoid arthritis on methotrexate.",
        profile_name="Eval Patient — Rheumatology Routine",
        doctors=[DoctorFixture(key="target", name="Dr. Laila Haddad", specialty="Rheumatology", clinic="Cascade Rheumatology")],
        target_doctor_key="target",
        appointment_purpose="Rheumatoid arthritis follow-up",
        appointment_scheduled_date="2026-09-01T11:00:00",
        conditions=[ConditionFixture(name="Rheumatoid Arthritis", icd_10="M06.9", status="active", severity="moderate")],
        medications=[
            MedicationFixture(name="Methotrexate", dosage="15mg", frequency="once weekly", prescribing_doctor_key="target", purpose="Disease-modifying therapy"),
        ],
    ),
    EvalCase(
        id="routine_pulmonology",
        description="Routine pulmonology follow-up for asthma on a maintenance inhaler.",
        profile_name="Eval Patient — Pulmonology Routine",
        doctors=[DoctorFixture(key="target", name="Dr. Owen Baptiste", specialty="Pulmonology", clinic="Summit Pulmonary Care")],
        target_doctor_key="target",
        appointment_purpose="Asthma follow-up",
        appointment_scheduled_date="2026-09-01T13:00:00",
        conditions=[ConditionFixture(name="Asthma", icd_10="J45.909", status="active")],
        medications=[
            MedicationFixture(name="Fluticasone/Salmeterol", dosage="250/50mcg", frequency="twice daily", prescribing_doctor_key="target", purpose="Asthma maintenance"),
        ],
    ),
    EvalCase(
        id="routine_obgyn",
        description="Routine OB/GYN follow-up for PCOS on an oral contraceptive.",
        profile_name="Eval Patient — OBGYN Routine",
        doctors=[DoctorFixture(key="target", name="Dr. Renata Cruz", specialty="Obstetrics & Gynecology", clinic="Willowbrook Women's Health")],
        target_doctor_key="target",
        appointment_purpose="PCOS follow-up",
        appointment_scheduled_date="2026-09-01T14:00:00",
        conditions=[ConditionFixture(name="Polycystic Ovary Syndrome", icd_10="E28.2", status="active")],
        medications=[
            MedicationFixture(name="Norethindrone/Ethinyl Estradiol", dosage="1mg/35mcg", frequency="once daily", prescribing_doctor_key="target", purpose="Cycle regulation"),
        ],
    ),
    EvalCase(
        id="routine_gastroenterology",
        description="Routine gastroenterology follow-up for GERD on a PPI.",
        profile_name="Eval Patient — GI Routine",
        doctors=[DoctorFixture(key="target", name="Dr. Marcus Feld", specialty="Gastroenterology", clinic="Riverbend GI Associates")],
        target_doctor_key="target",
        appointment_purpose="GERD follow-up",
        appointment_scheduled_date="2026-09-02T09:00:00",
        conditions=[ConditionFixture(name="Gastroesophageal Reflux Disease", icd_10="K21.9", status="active")],
        medications=[
            MedicationFixture(name="Omeprazole", dosage="20mg", frequency="once daily", prescribing_doctor_key="target", purpose="Acid suppression"),
        ],
    ),
    EvalCase(
        id="routine_nephrology",
        description="Routine nephrology follow-up for stage 2 CKD on an ACE inhibitor.",
        profile_name="Eval Patient — Nephrology Routine",
        doctors=[DoctorFixture(key="target", name="Dr. Ingrid Solberg", specialty="Nephrology", clinic="Meridian Kidney Care")],
        target_doctor_key="target",
        appointment_purpose="Chronic kidney disease follow-up",
        appointment_scheduled_date="2026-09-02T10:00:00",
        conditions=[ConditionFixture(name="Chronic Kidney Disease, Stage 2", icd_10="N18.2", status="active")],
        medications=[
            MedicationFixture(name="Lisinopril", dosage="10mg", frequency="once daily", prescribing_doctor_key="target", purpose="Blood pressure and renal protection"),
        ],
        lab_orders=[LabOrderFixture(test_name="Basic Metabolic Panel (eGFR)", ordered_date="2026-08-20")],
    ),
    EvalCase(
        id="routine_family_medicine_multicondition",
        description="Routine PCP follow-up for hypertension and hyperlipidemia, two conditions and two meds.",
        profile_name="Eval Patient — PCP Routine",
        doctors=[DoctorFixture(key="target", name="Dr. Alex Kim", specialty="Family Medicine", clinic="Riverside Family Practice")],
        target_doctor_key="target",
        appointment_purpose="Hypertension and cholesterol follow-up",
        appointment_scheduled_date="2026-09-02T11:00:00",
        conditions=[
            ConditionFixture(name="Essential Hypertension", icd_10="I10", status="active"),
            ConditionFixture(name="Hyperlipidemia", icd_10="E78.5", status="active"),
        ],
        medications=[
            MedicationFixture(name="Amlodipine", dosage="5mg", frequency="once daily", prescribing_doctor_key="target", purpose="Blood pressure control"),
            MedicationFixture(name="Atorvastatin", dosage="20mg", frequency="once daily at bedtime", prescribing_doctor_key="target", purpose="Cholesterol management"),
        ],
    ),
    EvalCase(
        id="routine_orthopedics",
        description="Routine orthopedics follow-up for knee osteoarthritis on an as-needed NSAID.",
        profile_name="Eval Patient — Orthopedics Routine",
        doctors=[DoctorFixture(key="target", name="Dr. Foster Reyes", specialty="Orthopedics", clinic="Granite Orthopedic Group")],
        target_doctor_key="target",
        appointment_purpose="Knee osteoarthritis follow-up",
        appointment_scheduled_date="2026-09-02T13:00:00",
        conditions=[ConditionFixture(name="Osteoarthritis, Right Knee", icd_10="M17.11", status="active", severity="mild")],
        medications=[
            MedicationFixture(name="Naproxen", dosage="500mg", frequency="as needed for pain", prescribing_doctor_key="target", purpose="Pain management"),
        ],
    ),
    EvalCase(
        id="routine_neurology",
        description="Routine neurology follow-up for migraine on a preventive medication.",
        profile_name="Eval Patient — Neurology Routine",
        doctors=[DoctorFixture(key="target", name="Dr. Beatrice Lund", specialty="Neurology", clinic="Cedar Neurology Clinic")],
        target_doctor_key="target",
        appointment_purpose="Migraine follow-up",
        appointment_scheduled_date="2026-09-02T14:00:00",
        conditions=[ConditionFixture(name="Chronic Migraine", icd_10="G43.709", status="active")],
        medications=[
            MedicationFixture(name="Topiramate", dosage="50mg", frequency="twice daily", prescribing_doctor_key="target", purpose="Migraine prevention"),
        ],
    ),
    EvalCase(
        id="routine_ophthalmology",
        description="Routine ophthalmology follow-up for glaucoma on daily eye drops.",
        profile_name="Eval Patient — Ophthalmology Routine",
        doctors=[DoctorFixture(key="target", name="Dr. Nadia Petrov", specialty="Ophthalmology", clinic="Clearview Eye Institute")],
        target_doctor_key="target",
        appointment_purpose="Glaucoma follow-up",
        appointment_scheduled_date="2026-09-03T09:00:00",
        conditions=[ConditionFixture(name="Primary Open-Angle Glaucoma", icd_10="H40.11X1", status="active")],
        medications=[
            MedicationFixture(name="Latanoprost", dosage="0.005%", frequency="once daily at bedtime, both eyes", prescribing_doctor_key="target", purpose="Intraocular pressure control"),
        ],
    ),
    EvalCase(
        id="routine_ent",
        description="Routine ENT follow-up for chronic sinusitis on a daily nasal spray.",
        profile_name="Eval Patient — ENT Routine",
        doctors=[DoctorFixture(key="target", name="Dr. Marcus Webb", specialty="Otolaryngology", clinic="Bayshore ENT")],
        target_doctor_key="target",
        appointment_purpose="Chronic sinusitis follow-up",
        appointment_scheduled_date="2026-09-03T10:00:00",
        conditions=[ConditionFixture(name="Chronic Sinusitis", icd_10="J32.9", status="active")],
        medications=[
            MedicationFixture(name="Fluticasone Nasal Spray", dosage="50mcg/spray", frequency="twice daily, both nostrils", prescribing_doctor_key="target", purpose="Sinus inflammation control"),
        ],
    ),
]

# ── Tier B: 8 targeted edge-case probes not covered by the original 5 ──────

_TIER_B = [
    EvalCase(
        id="inactive_condition_not_active_management",
        description=(
            "Patient has one resolved condition and one active condition; the "
            "resolved one should not generate active-management questions."
        ),
        profile_name="Eval Patient — Inactive Condition",
        doctors=[DoctorFixture(key="target", name="Dr. Elena Vance", specialty="Endocrinology", clinic="Bay Endocrinology")],
        target_doctor_key="target",
        appointment_purpose="Diabetes follow-up",
        appointment_scheduled_date="2026-09-03T11:00:00",
        conditions=[
            ConditionFixture(name="Type 2 Diabetes Mellitus", icd_10="E11.9", status="active"),
            ConditionFixture(name="Gestational Diabetes", icd_10="O24.4", status="resolved", notes="Resolved after delivery, 2023."),
        ],
        medications=[
            MedicationFixture(name="Metformin", dosage="500mg", frequency="twice daily", prescribing_doctor_key="target", purpose="Blood sugar control"),
        ],
    ),
    EvalCase(
        id="medication_mentioned_only_in_past_notes",
        description=(
            "A medication was discontinued and is only mentioned in a past "
            "visit's notes, not in the current medication list — the "
            "generated output should not treat it as an ongoing medication."
        ),
        profile_name="Eval Patient — Discontinued Med Mention",
        doctors=[DoctorFixture(key="target", name="Dr. Foster Reyes", specialty="Orthopedics", clinic="Granite Orthopedic Group")],
        target_doctor_key="target",
        appointment_purpose="Knee pain follow-up",
        appointment_scheduled_date="2026-09-03T13:00:00",
        conditions=[ConditionFixture(name="Osteoarthritis, Right Knee", icd_10="M17.11", status="active")],
        past_visits=[
            PastVisitFixture(
                doctor_key="target", scheduled_date="2026-06-01T13:00:00",
                purpose="Knee pain follow-up",
                visit_notes="Discontinued Ibuprofen due to GI upset; advised acetaminophen as needed instead, not currently prescribed.",
            ),
        ],
    ),
    EvalCase(
        id="excluded_doctor_relevant_history",
        description=(
            "A doctor with clearly relevant history is marked "
            "exclude_from_prep_context — checks that excluded context "
            "genuinely doesn't leak into the generated output."
        ),
        profile_name="Eval Patient — Excluded Doctor",
        doctors=[
            DoctorFixture(key="target", name="Dr. Elena Vance", specialty="Endocrinology", clinic="Bay Endocrinology"),
            DoctorFixture(key="excluded", name="Dr. Old Provider", specialty="Endocrinology", clinic="Former Clinic", exclude_from_prep_context=True),
        ],
        target_doctor_key="target",
        appointment_purpose="Thyroid follow-up",
        appointment_scheduled_date="2026-09-03T14:00:00",
        conditions=[ConditionFixture(name="Hashimoto's Thyroiditis", icd_10="E06.3", status="active")],
        medications=[
            MedicationFixture(name="Levothyroxine", dosage="75mcg", frequency="once daily, morning", prescribing_doctor_key="target", purpose="Thyroid hormone replacement"),
        ],
        past_visits=[
            PastVisitFixture(
                doctor_key="excluded", scheduled_date="2026-01-15T10:00:00",
                purpose="Initial thyroid workup",
                visit_notes="Confidential note from prior provider — should not surface in visit-prep context.",
            ),
        ],
    ),
    EvalCase(
        id="conflicting_cross_visit_notes",
        description=(
            "Two past visits with the target doctor whose notes are in "
            "mild tension (one implies a recent dose change, the other says "
            "unchanged) — tests whether the model hedges rather than "
            "asserting either as settled fact."
        ),
        profile_name="Eval Patient — Conflicting Notes",
        doctors=[DoctorFixture(key="target", name="Dr. Elena Vance", specialty="Endocrinology", clinic="Bay Endocrinology")],
        target_doctor_key="target",
        appointment_purpose="Thyroid follow-up",
        appointment_scheduled_date="2026-09-04T09:00:00",
        conditions=[ConditionFixture(name="Hashimoto's Thyroiditis", icd_10="E06.3", status="active")],
        medications=[
            MedicationFixture(name="Levothyroxine", dosage="75mcg", frequency="once daily, morning", prescribing_doctor_key="target", purpose="Thyroid hormone replacement"),
        ],
        past_visits=[
            PastVisitFixture(
                doctor_key="target", scheduled_date="2026-07-01T09:00:00",
                purpose="Thyroid follow-up", visit_notes="Dose unchanged at 75mcg; TSH stable.",
            ),
            PastVisitFixture(
                doctor_key="target", scheduled_date="2026-05-01T09:00:00",
                purpose="Thyroid follow-up", visit_notes="Discussed possibly increasing dose pending next TSH; patient to follow up.",
            ),
        ],
    ),
    EvalCase(
        id="referral_carryover_unconfirmed",
        description=(
            "A past visit's notes mention a planned referral; the next "
            "visit's notes are silent on it — a real carryover the model "
            "should surface as a follow-up question."
        ),
        profile_name="Eval Patient — Referral Carryover",
        doctors=[DoctorFixture(key="target", name="Dr. Ingrid Solberg", specialty="Nephrology", clinic="Meridian Kidney Care")],
        target_doctor_key="target",
        appointment_purpose="CKD follow-up",
        appointment_scheduled_date="2026-09-04T10:00:00",
        conditions=[ConditionFixture(name="Chronic Kidney Disease, Stage 3", icd_10="N18.3", status="active")],
        medications=[
            MedicationFixture(name="Lisinopril", dosage="10mg", frequency="once daily", prescribing_doctor_key="target", purpose="Blood pressure and renal protection"),
        ],
        past_visits=[
            PastVisitFixture(
                doctor_key="target", scheduled_date="2026-06-01T10:00:00",
                purpose="CKD follow-up",
                visit_notes="Planned to discuss: referral to a renal dietitian for dietary management.",
            ),
            PastVisitFixture(
                doctor_key="target", scheduled_date="2026-07-15T10:00:00",
                purpose="CKD follow-up",
                visit_notes="eGFR stable. Discussed hydration and blood pressure control.",
            ),
        ],
    ),
    EvalCase(
        id="labs_mixed_temporal_status",
        description=(
            "Multiple lab orders at different ages, some recently ordered "
            "and some overdue for follow-up — tests whether temporal "
            "qualifiers are used correctly rather than presupposing results."
        ),
        profile_name="Eval Patient — Mixed Lab Timing",
        doctors=[DoctorFixture(key="target", name="Dr. Marcus Feld", specialty="Gastroenterology", clinic="Riverbend GI Associates")],
        target_doctor_key="target",
        appointment_purpose="IBD follow-up",
        appointment_scheduled_date="2026-09-04T11:00:00",
        conditions=[ConditionFixture(name="Crohn's Disease", icd_10="K50.90", status="active")],
        medications=[
            MedicationFixture(name="Mesalamine", dosage="1.2g", frequency="three times daily", prescribing_doctor_key="target", purpose="Maintenance therapy"),
        ],
        lab_orders=[
            LabOrderFixture(test_name="C-Reactive Protein", ordered_date="2026-08-25"),
            LabOrderFixture(test_name="Fecal Calprotectin", ordered_date="2026-03-01"),
        ],
    ),
    EvalCase(
        id="same_specialty_switched_doctors",
        description=(
            "Patient switched cardiologists; past visits exist with both "
            "the target doctor and a prior same-specialty doctor — tests "
            "same-doctor-only-most-recent handling in a non-unit-test case."
        ),
        profile_name="Eval Patient — Switched Doctors",
        doctors=[
            DoctorFixture(key="target", name="Dr. Priya Nair", specialty="Cardiology", clinic="Harborview Cardiology"),
            DoctorFixture(key="prior", name="Dr. Older Cardiologist", specialty="Cardiology", clinic="Former Cardiology Group"),
        ],
        target_doctor_key="target",
        appointment_purpose="Atrial fibrillation follow-up",
        appointment_scheduled_date="2026-09-04T13:00:00",
        conditions=[ConditionFixture(name="Atrial Fibrillation", icd_10="I48.91", status="active")],
        medications=[
            MedicationFixture(name="Apixaban", dosage="5mg", frequency="twice daily", prescribing_doctor_key="target", purpose="Stroke prevention"),
        ],
        past_visits=[
            PastVisitFixture(doctor_key="target", scheduled_date="2026-07-01T13:00:00", purpose="AFib follow-up", visit_notes="Rate well-controlled on current regimen."),
            PastVisitFixture(doctor_key="prior", scheduled_date="2025-12-01T13:00:00", purpose="Initial AFib diagnosis", visit_notes="Started on anticoagulation."),
        ],
    ),
    EvalCase(
        id="condition_severity_variation",
        description=(
            "A condition explicitly marked severe — tests whether severity "
            "influences question specificity without inventing facts beyond "
            "what the severity field states."
        ),
        profile_name="Eval Patient — Severity Marked",
        doctors=[DoctorFixture(key="target", name="Dr. Owen Baptiste", specialty="Pulmonology", clinic="Summit Pulmonary Care")],
        target_doctor_key="target",
        appointment_purpose="Severe asthma follow-up",
        appointment_scheduled_date="2026-09-04T14:00:00",
        conditions=[ConditionFixture(name="Asthma", icd_10="J45.909", status="active", severity="severe", notes="Two ER visits in the past 6 months.")],
        medications=[
            MedicationFixture(name="Fluticasone/Salmeterol", dosage="500/50mcg", frequency="twice daily", prescribing_doctor_key="target", purpose="Asthma maintenance"),
            MedicationFixture(name="Albuterol", dosage="90mcg", frequency="as needed", prescribing_doctor_key="target", purpose="Rescue inhaler"),
        ],
    ),
]

# ── Tier C: 5 data-extreme stress cases ─────────────────────────────────────

_TIER_C = [
    EvalCase(
        id="max_density_multi_comorbidity",
        description=(
            "Dense profile: 4 conditions, 5 medications, multiple labs, and "
            "a long past-visit history — stresses context-selection budget "
            "and the 15-question ceiling simultaneously."
        ),
        profile_name="Eval Patient — Max Density",
        doctors=[DoctorFixture(key="target", name="Dr. Elena Vance", specialty="Endocrinology", clinic="Bay Endocrinology")],
        target_doctor_key="target",
        appointment_purpose="Comprehensive endocrine follow-up",
        appointment_scheduled_date="2026-09-05T09:00:00",
        conditions=[
            ConditionFixture(name="Type 2 Diabetes Mellitus", icd_10="E11.9", status="active"),
            ConditionFixture(name="Hashimoto's Thyroiditis", icd_10="E06.3", status="active"),
            ConditionFixture(name="Essential Hypertension", icd_10="I10", status="active"),
            ConditionFixture(name="Hyperlipidemia", icd_10="E78.5", status="active"),
        ],
        medications=[
            MedicationFixture(name="Metformin", dosage="1000mg", frequency="twice daily", prescribing_doctor_key="target", purpose="Blood sugar control"),
            MedicationFixture(name="Levothyroxine", dosage="88mcg", frequency="once daily, morning", prescribing_doctor_key="target", purpose="Thyroid hormone replacement"),
            MedicationFixture(name="Lisinopril", dosage="20mg", frequency="once daily", prescribing_doctor_key="target", purpose="Blood pressure control"),
            MedicationFixture(name="Atorvastatin", dosage="40mg", frequency="once daily at bedtime", prescribing_doctor_key="target", purpose="Cholesterol management"),
            MedicationFixture(name="Empagliflozin", dosage="10mg", frequency="once daily", prescribing_doctor_key="target", purpose="Glycemic and cardiorenal protection"),
        ],
        lab_orders=[
            LabOrderFixture(test_name="HbA1c", ordered_date="2026-08-20"),
            LabOrderFixture(test_name="TSH", ordered_date="2026-08-20"),
            LabOrderFixture(test_name="Lipid Panel", ordered_date="2026-07-01"),
        ],
        vitals=[
            VitalsFixture(weight="210 lbs", bmi=31.4, blood_pressure="134/86", measured_date="2026-08-20"),
        ],
        past_visits=[
            PastVisitFixture(doctor_key="target", scheduled_date="2026-05-15T09:00:00", purpose="Diabetes follow-up", visit_notes="A1C improved from 8.1 to 7.4."),
            PastVisitFixture(doctor_key="target", scheduled_date="2026-02-15T09:00:00", purpose="Diabetes follow-up", visit_notes="Started Empagliflozin."),
        ],
    ),
    EvalCase(
        id="minimal_single_condition_single_med",
        description=(
            "One condition, one medication, nothing else — a step above "
            "cold_start's zero-medication case, testing the floor with "
            "just barely enough data. Deliberately a different specialty/"
            "condition from any other case in this set (was previously a "
            "near-duplicate of routine_neurology's migraine/Topiramate "
            "profile — swapped to avoid overlapping coverage)."
        ),
        profile_name="Eval Patient — Minimal Plus One",
        doctors=[DoctorFixture(key="target", name="Dr. Priya Malhotra", specialty="Dermatology", clinic="Clearskin Dermatology")],
        target_doctor_key="target",
        appointment_purpose="Eczema follow-up",
        appointment_scheduled_date="2026-09-05T10:00:00",
        conditions=[ConditionFixture(name="Atopic Dermatitis", icd_10="L20.9", status="active")],
        medications=[
            MedicationFixture(name="Tacrolimus Ointment", dosage="0.1%", frequency="twice daily", prescribing_doctor_key="target", purpose="Eczema flare control"),
        ],
    ),
    EvalCase(
        id="many_irrelevant_past_visits",
        description=(
            "Several past visits, all with an unrelated-specialty doctor — "
            "tests retrieval filtering under volume, distinct from "
            "retrieval_redundancy's same-doctor case. Deliberately a "
            "different specialty/condition from any other case in this set "
            "(was previously a near-duplicate of routine_ophthalmology's "
            "glaucoma/Latanoprost profile — swapped to avoid overlapping "
            "coverage)."
        ),
        profile_name="Eval Patient — Irrelevant History Volume",
        doctors=[
            DoctorFixture(key="target", name="Dr. Victor Amado", specialty="Urology", clinic="Meridian Urology Associates"),
            DoctorFixture(key="derm", name="Dr. Rita Fields", specialty="Dermatology", clinic="Clearskin Dermatology"),
        ],
        target_doctor_key="target",
        appointment_purpose="Benign prostatic hyperplasia follow-up",
        appointment_scheduled_date="2026-09-05T11:00:00",
        conditions=[ConditionFixture(name="Benign Prostatic Hyperplasia", icd_10="N40.1", status="active")],
        medications=[
            MedicationFixture(name="Tamsulosin", dosage="0.4mg", frequency="once daily", prescribing_doctor_key="target", purpose="Urinary symptom control"),
        ],
        past_visits=[
            PastVisitFixture(doctor_key="derm", scheduled_date="2026-06-01T11:00:00", purpose="Acne follow-up", visit_notes="Improved with current regimen."),
            PastVisitFixture(doctor_key="derm", scheduled_date="2026-03-01T11:00:00", purpose="Acne follow-up", visit_notes="Started topical retinoid."),
            PastVisitFixture(doctor_key="derm", scheduled_date="2025-12-01T11:00:00", purpose="New patient dermatology visit", visit_notes="Initial acne assessment."),
        ],
    ),
    EvalCase(
        id="vitals_only_no_labs",
        description=(
            "A vitals trend present with no lab orders at all — isolates "
            "vitals-only grounding, distinct from groundedness_labs_vitals "
            "which has both."
        ),
        profile_name="Eval Patient — Vitals Only",
        doctors=[DoctorFixture(key="target", name="Dr. Alex Kim", specialty="Family Medicine", clinic="Riverside Family Practice")],
        target_doctor_key="target",
        appointment_purpose="Weight management follow-up",
        appointment_scheduled_date="2026-09-05T13:00:00",
        conditions=[ConditionFixture(name="Overweight", icd_10="E66.3", status="active")],
        vitals=[
            VitalsFixture(weight="195 lbs", bmi=28.9, blood_pressure="128/82", measured_date="2026-08-15"),
            VitalsFixture(weight="201 lbs", bmi=29.8, blood_pressure="130/84", measured_date="2026-05-15"),
        ],
    ),
    EvalCase(
        id="all_out_of_scope_for_specialty",
        description=(
            "Every condition and medication is out of scope for the target "
            "specialty — an extreme version of cross_specialty_scope. "
            "Every category should legitimately have little or nothing to "
            "say; tests whether the model produces a short, honest list "
            "instead of padding with off-scope or invented content."
        ),
        profile_name="Eval Patient — All Out Of Scope",
        doctors=[
            DoctorFixture(key="target", name="Dr. Nadia Petrov", specialty="Ophthalmology", clinic="Clearview Eye Institute"),
            DoctorFixture(key="derm", name="Dr. Rita Fields", specialty="Dermatology", clinic="Clearskin Dermatology"),
            DoctorFixture(key="pcp", name="Dr. Alex Kim", specialty="Family Medicine", clinic="Riverside Family Practice"),
        ],
        target_doctor_key="target",
        appointment_purpose="Annual eye exam",
        appointment_scheduled_date="2026-09-05T14:00:00",
        conditions=[
            ConditionFixture(name="Mild Plaque Psoriasis", icd_10="L40.0", status="active", in_scope=False),
            ConditionFixture(name="Essential Hypertension", icd_10="I10", status="active", in_scope=False),
        ],
        medications=[
            MedicationFixture(name="Clobetasol Cream", dosage="0.05%", frequency="once daily", prescribing_doctor_key="derm", purpose="Psoriasis flare control"),
            MedicationFixture(name="Amlodipine", dosage="5mg", frequency="once daily", prescribing_doctor_key="pcp", purpose="Blood pressure control"),
        ],
    ),
]

REVIEW_STUDY_CASES: list[EvalCase] = _TIER_A + _TIER_B + _TIER_C

assert len(REVIEW_STUDY_CASES) == 25
assert len({c.id for c in REVIEW_STUDY_CASES}) == 25, "duplicate case id in REVIEW_STUDY_CASES"
