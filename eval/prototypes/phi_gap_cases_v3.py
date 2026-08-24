"""Corpus for the HIPAA Safe Harbor coverage-gap follow-up (issue #122 lineage).

**Prototype/evaluation data only** — same non-production guarantee as the other
files in `eval/prototypes/`.

## Why this corpus exists

Comparing `src/utils/anonymization.py`'s `PII_PATTERNS` against HIPAA Safe
Harbor's 18 identifier categories found several categories with no dedicated
pattern at all: URLs, IP addresses, certificate/license numbers, generic
account numbers (only caught incidentally, and only the digit portion when an
alphanumeric prefix is present — `"AB-9284710"` redacts to `"AB-[REDACTED]"`),
vehicle identifiers (VIN), and device serial numbers. Biometric identifiers and
full-face photographs are treated as genuinely out of scope — this is a
text-only AVS parser with no image/biometric ingestion — and are not covered
here.

This corpus tests six categories: `url`, `ip_address`, `license_number`,
`account_number`, `vehicle_id`, `device_serial`. Smaller than v1/v2 by design —
these are narrow, individually-testable format gaps, not broad free-text
categories needing dozens of natural-language variations to stress.
"""

from eval.prototypes.openmed_pii_cases import NegativeCase, PositiveCase

POSITIVE_CASES: tuple[PositiveCase, ...] = (
    PositiveCase(
        "See the patient portal at https://portal.healthsteward.example/records/8823 for full results.",
        ("https://portal.healthsteward.example/records/8823",), "url",
    ),
    PositiveCase(
        "Telehealth visit link was https://meet.clinicvideo.example/room/nm-4471 sent by text.",
        ("https://meet.clinicvideo.example/room/nm-4471",), "url",
    ),
    PositiveCase(
        "Records request confirmation is available at http://records.example-clinic.com/req/33210.",
        ("http://records.example-clinic.com/req/33210",), "url",
    ),
    PositiveCase(
        "Login attempt was logged from IP 192.168.1.42 during the telehealth session.",
        ("192.168.1.42",), "ip_address",
    ),
    PositiveCase(
        "Session originated from 203.0.113.77, flagged for review by the portal's audit log.",
        ("203.0.113.77",), "ip_address",
    ),
    PositiveCase(
        "Patient's home network address on the visit-day connection log was 10.44.201.9.",
        ("10.44.201.9",), "ip_address",
    ),
    PositiveCase(
        "Driver's License Number: D1234567 was used to verify identity at check-in.",
        ("D1234567",), "license_number",
    ),
    PositiveCase(
        "Certificate Number: CRT-88213 confirms the completed occupational therapy course.",
        ("CRT-88213",), "license_number",
    ),
    PositiveCase(
        "License No. RN-4471029 was recorded for the visiting home-health nurse.",
        ("RN-4471029",), "license_number",
    ),
    PositiveCase(
        "Billing account number AB-9284710 was updated after the payment posted.",
        ("AB-9284710",), "account_number",
    ),
    PositiveCase(
        "Statements are mailed against Account Number: 7734190552 going forward.",
        ("7734190552",), "account_number",
    ),
    PositiveCase(
        "Refund was applied to account no. XZ-330912 per the billing department.",
        ("XZ-330912",), "account_number",
    ),
    PositiveCase(
        "Transport service logged VIN: 1HGCM82633A123456 for the wheelchair van pickup.",
        ("1HGCM82633A123456",), "vehicle_id",
    ),
    PositiveCase(
        "Medical transport VIN 2FMDK3GC4BBA12345 was assigned for the discharge ride home.",
        ("2FMDK3GC4BBA12345",), "vehicle_id",
    ),
    PositiveCase(
        "Device Serial Number: SN-88213047 was replaced during today's equipment check.",
        ("SN-88213047",), "device_serial",
    ),
    PositiveCase(
        "Serial No: CGM-771402 identifies the continuous glucose monitor issued at discharge.",
        ("CGM-771402",), "device_serial",
    ),
    PositiveCase(
        "Pump Serial Number 8842910337 was logged when the insulin pump was fitted.",
        ("8842910337",), "device_serial",
    ),
    # Fax (#5) is already caught by the existing `phone` pattern by format
    # coincidence (a fax number has no distinct format of its own) — this
    # gives that an explicit, checkable test case instead of leaving it
    # asserted-but-untested.
    PositiveCase(
        "Records were sent to Fax: 555-201-4487 per the referral request.",
        ("555-201-4487",), "fax",
    ),
    # #18's catch-all is inherently open-ended and can't be "completed" by a
    # fixed corpus — these two are representative examples, not exhaustive
    # coverage of "any other unique identifying number or code."
    PositiveCase(
        "Study Participant ID: SP-7734029 links this visit to the trial dataset.",
        ("SP-7734029",), "other_unique_id",
    ),
    PositiveCase(
        "Case Reference Number CRN-2026-88213 was assigned by the review board.",
        ("CRN-2026-88213",), "other_unique_id",
    ),
)

NEGATIVE_CASES: tuple[NegativeCase, ...] = (
    NegativeCase("Blood pressure today was 128/82, heart rate 76, temperature 98.4F.", "vitals"),
    NegativeCase("A1c improved to 6.8% from 7.4% three months ago.", "labs"),
    NegativeCase("Continue Lisinopril 10 mg daily for blood pressure control.", "medication"),
    NegativeCase("Weight 185 lbs, BMI 27.3, otherwise unremarkable exam.", "vitals"),
    NegativeCase("Chart reviewed for the patient; no acute changes since the last encounter.", "note"),
    NegativeCase("Fasting glucose was 104 mg/dL, borderline but stable.", "labs"),
    NegativeCase("Diagnosis: Type 2 diabetes mellitus, well controlled on current regimen.", "condition"),
    NegativeCase("Plan: continue current medications, recheck labs in three months.", "plan"),
    NegativeCase("Ratio of systolic to diastolic pressure trended down over the visit.", "vitals"),
    NegativeCase("Ordered a basic metabolic panel and lipid panel for the next visit.", "labs"),
)

ALL_CATEGORIES = tuple(
    sorted({c.category for c in POSITIVE_CASES} | {c.category for c in NEGATIVE_CASES})
)
