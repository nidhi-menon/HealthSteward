"""Bias-corrected benchmark corpus for the OpenMed PII re-run (issue #122 follow-up).

**Prototype/evaluation data only** — same non-production guarantee as
`openmed_pii_cases.py`: nothing here is imported by `src/` or collected by
`tests/`.

## Why this corpus exists alongside `openmed_pii_cases.py`

The original OpenMed benchmark (PR #124, `OPENMED_FINDINGS.md`) transcribed its
corpus from `tests/test_anonymization.py` — the regex implementation's own test
suite. That corpus is dense with the exact-format edge cases regex is *defined*
to catch (`Call me at 555-123-4567`) and light on the free-text, in-sentence PII
that NER-style models like OpenMed actually target. Scoring OpenMed against a
corpus built to specify a competing approach structurally favors that approach.

This file is written independently: every case is an original clinical-note
sentence with PII embedded in context, the way it would actually appear in a
visit note or intake form, rather than a bare pattern fragment. It does not
replace `openmed_pii_cases.py` — the harness runs both corpora and reports them
separately, so a reader can see whether a system's ranking holds up once the
"home-field" bias of the original corpus is removed.

Same two case kinds as the original corpus:

- `PositiveCase` — text containing PII. `must_remove` lists the exact
  substrings that must not survive redaction (a **leak**).
- `NegativeCase` — clinical text with no PII, which must round-trip
  byte-identical (redacting it is **over-redaction**).

Per-category sample sizes here are larger than the original corpus's most
sparse categories, but still small enough that single-case swings matter for
some categories — the report should still be read per-category, not as one
number.
"""

from eval.prototypes.openmed_pii_cases import NegativeCase, PositiveCase

POSITIVE_CASES: tuple[PositiveCase, ...] = (
    PositiveCase("Patient Maria Garcia was counseled on the importance of medication adherence during today's visit.", ('Maria Garcia',), 'person_name'),
    PositiveCase('James Thompson reports the shoulder pain has improved since starting physical therapy.', ('James Thompson',), 'person_name'),
    PositiveCase('Discussed lab results with Aisha Khan over the phone this afternoon.', ('Aisha Khan',), 'person_name'),
    PositiveCase('Wei Chen will follow up with the referring specialist in three weeks.', ('Wei Chen',), 'person_name'),
    PositiveCase('Chart reviewed for Robert Patel; no acute changes noted since the last encounter.', ('Robert Patel',), 'person_name'),
    PositiveCase('Priya Nguyen arrived on time and denied any new symptoms since discharge.', ('Priya Nguyen',), 'person_name'),
    PositiveCase('Nursing staff assisted Daniel Silva with the pre-visit intake questionnaire.', ('Daniel Silva',), 'person_name'),
    PositiveCase("Fatima Okafor was accompanied by a family member for today's appointment.", ('Fatima Okafor',), 'person_name'),
    PositiveCase('Please have the patient call the clinic back at 555-201-4487 to confirm the referral.', ('555-201-4487',), 'phone'),
    PositiveCase('Left a voicemail for the patient at (555) 340-9821 regarding the pending lab results.', ('(555) 340-9821',), 'phone'),
    PositiveCase('Emergency contact can be reached at 555.772.6630 if needed after hours.', ('555.772.6630',), 'phone'),
    PositiveCase('Pharmacy confirmed the refill and left a callback number of 555-908-1123.', ('555-908-1123',), 'phone'),
    PositiveCase("Patient's cell phone on file is (555) 614-2290; text reminders enabled.", ('(555) 614-2290',), 'phone'),
    PositiveCase('Front desk noted the updated contact number as 555-201-4487 in the chart.', ('555-201-4487',), 'phone'),
    PositiveCase('Patient is traveling abroad and can be reached at +44 20 7946 0958 until next month.', ('+44 20 7946 0958',), 'phone_intl'),
    PositiveCase('International emergency contact (spouse) phone: +91 98765 43210.', ('+91 98765 43210',), 'phone_intl'),
    PositiveCase('Records request faxed to the overseas clinic, callback +61 2 9374 4000.', ('+61 2 9374 4000',), 'phone_intl'),
    PositiveCase('Patient relocated overseas; new contact line is +49 30 1234 5678.', ('+49 30 1234 5678',), 'phone_intl'),
    PositiveCase("Visit summary was sent to the patient's email, m.garcia87@fastmail.com, per their request.", ('m.garcia87@fastmail.com',), 'email'),
    PositiveCase('Patient prefers electronic communication and can be reached at j.thompson.med@outlook.com.', ('j.thompson.med@outlook.com',), 'email'),
    PositiveCase('Portal invitation resent to aisha.khan91@gmail.com after the first message bounced.', ('aisha.khan91@gmail.com',), 'email'),
    PositiveCase('Lab results were shared securely via the portal linked to wpatel.contact@yahoo.com.', ('wpatel.contact@yahoo.com',), 'email'),
    PositiveCase("Insurance verification required the patient's SSN, recorded as 512-88-3347 for the claim.", ('512-88-3347',), 'ssn'),
    PositiveCase('Social Security Number on file for billing purposes: 603-14-9926.', ('603-14-9926',), 'ssn'),
    PositiveCase("Disability paperwork lists the patient's SSN as 778-22-5510.", ('778-22-5510',), 'ssn'),
    PositiveCase("Patient's home address is 1420 Maple Avenue, Springfield, IL 62704, per the intake form.", ('1420 Maple Avenue',), 'address'),
    PositiveCase('Durable medical equipment will be delivered to 88 Birchwood Lane, Portland, OR.', ('88 Birchwood Lane',), 'address'),
    PositiveCase('Home health referral sent to the residence at 215 Riverside Drive, Asheville NC 28801.', ('215 Riverside Drive',), 'address'),
    PositiveCase('Updated mailing address on file: 5 Fenwick Court, Boulder, CO 80302.', ('5 Fenwick Court',), 'address'),
    PositiveCase('Patient recently moved to 3301 Sunset Boulevard in Naperville, IL; records forwarded.', ('3301 Sunset Boulevard',), 'address'),
    PositiveCase('Visiting nurse scheduled to see the patient at 77 Alder Street, Bellevue.', ('77 Alder Street',), 'address'),
    PositiveCase('Billing address zip code updated to 62704 after the recent move.', ('62704',), 'zip'),
    PositiveCase("Patient's mailing zip is 97205; confirmed with front desk.", ('97205',), 'zip'),
    PositiveCase("Statements should be mailed to P.O. Box 1000, per the patient's request.", ('P.O. Box 1000',), 'po_box'),
    PositiveCase("Patient's mailing address for correspondence is P.O. Box 1037.", ('P.O. Box 1037',), 'po_box'),
    PositiveCase('Insurance card was mailed back to P.O. Box 1074 as undeliverable.', ('P.O. Box 1074',), 'po_box'),
    PositiveCase("Patient's date of birth is 03/14/1979, confirmed against the insurance card.", ('03/14/1979',), 'date'),
    PositiveCase('Born November 2, 1985, patient is now due for the age-appropriate screening panel.', ('November 2, 1985',), 'date'),
    PositiveCase('DOB 1991-06-30 verified with photo ID at check-in.', ('1991-06-30',), 'date'),
    PositiveCase("MRN 88213047; chart pulled for review ahead of today's appointment.", ('88213047',), 'mrn_labeled'),
    PositiveCase('Records department located the file under Medical Record Number: 7734190.', ('7734190',), 'mrn_labeled'),
    PositiveCase("Referral paperwork lists the patient's Chart #5591203 at the top of the page.", ('5591203',), 'mrn_labeled'),
    PositiveCase("MR# 9012384 was used to cross-reference the outside hospital's imaging report.", ('9012384',), 'mrn_labeled'),
    PositiveCase('Policy #: BXQ-77419203; verified as active with a $30 copay for specialist visits.', ('BXQ-77419203',), 'insurance_id'),
    PositiveCase('Prior authorization submitted using Member ID 4482910573.', ('4482910573',), 'insurance_id'),
    PositiveCase('Group Number: 331-CIGNA-9 was confirmed over the phone with the insurance carrier.', ('331-CIGNA-9',), 'insurance_id'),
    PositiveCase('Claims department requested confirmation of Subscriber ID: HMK7729014 before processing.', ('HMK7729014',), 'insurance_id'),
    PositiveCase('Called Maria Garcia at 555-201-4487 to reschedule; confirmed mailing address as 1420 Maple Avenue, Springfield, IL 62704.', ('Maria Garcia', '555-201-4487', '1420 Maple Avenue'), 'mixed_note'),
    PositiveCase('James Thompson (Medical Record Number: 7734190) emailed j.thompson.med@outlook.com asking about the results discussed on November 2, 1985.', ('James Thompson',), 'mixed_note'),
    PositiveCase('Insurance for Aisha Khan, Group Number: 331-CIGNA-9, was verified after a callback to 555.772.6630.', ('Aisha Khan', '555.772.6630'), 'mixed_note'),
)

NEGATIVE_CASES: tuple[NegativeCase, ...] = (
    NegativeCase('Blood pressure today was 128/82, heart rate 76, temperature 98.4F.', 'vitals'),
    NegativeCase('Weight is up 4 lbs since the last visit, now 172 lbs; BMI 27.3.', 'vitals'),
    NegativeCase('Oxygen saturation was 97% on room air at rest.', 'vitals'),
    NegativeCase('Respiratory rate 18, afebrile, pulse regular at 68 bpm.', 'vitals'),
    NegativeCase('Height 5\'6", weight 154 lbs, BMI within normal limits.', 'vitals'),
    NegativeCase('Repeat blood pressure after five minutes rest was 122/78.', 'vitals'),
    NegativeCase('A1c improved to 6.8% from 7.4% three months ago.', 'labs'),
    NegativeCase('LDL cholesterol is 118 mg/dL, within goal on current statin dose.', 'labs'),
    NegativeCase('CBC shows mild leukocytosis at 11.2, otherwise unremarkable.', 'labs'),
    NegativeCase('TSH within normal range at 2.1 mIU/L; no dose adjustment needed.', 'labs'),
    NegativeCase('Fasting glucose was 104 mg/dL, borderline but stable.', 'labs'),
    NegativeCase('Creatinine 0.9 mg/dL, eGFR >60; renal function stable.', 'labs'),
    NegativeCase('Potassium slightly elevated at 5.1 mEq/L, recheck in one week.', 'labs'),
    NegativeCase('Continue Lisinopril 10 mg daily for blood pressure control.', 'medication'),
    NegativeCase('Metformin increased to 1000 mg twice daily with meals.', 'medication'),
    NegativeCase('Started Atorvastatin 20 mg at bedtime for hyperlipidemia.', 'medication'),
    NegativeCase('Discontinued Ibuprofen due to GI upset; switched to acetaminophen.', 'medication'),
    NegativeCase('Albuterol inhaler as needed for wheeze, up to every four hours.', 'medication'),
    NegativeCase('Amoxicillin 500 mg three times daily for ten days.', 'dosage'),
    NegativeCase('Increase Levothyroxine to 75 mcg each morning on an empty stomach.', 'dosage'),
    NegativeCase('Prednisone taper: 40 mg for 3 days, then 20 mg for 3 days.', 'dosage'),
    NegativeCase('Insulin glargine 22 units at bedtime, adjusted from 18 units.', 'dosage'),
    NegativeCase('Diagnosis: Type 2 diabetes mellitus, well controlled.', 'condition'),
    NegativeCase('Assessment: seasonal allergic rhinitis, symptomatic.', 'condition'),
    NegativeCase('History of hypertension and hyperlipidemia, both stable.', 'condition'),
    NegativeCase('Chronic lower back pain, likely mechanical in origin.', 'condition'),
    NegativeCase('Mild intermittent asthma, no exacerbations in six months.', 'condition'),
    NegativeCase('Next appointment scheduled for a follow-up in six weeks.', 'scheduling'),
    NegativeCase('Please return in three months for repeat lab work.', 'scheduling'),
    NegativeCase('Recommend annual wellness visit be scheduled next spring.', 'scheduling'),
    NegativeCase('Follow-up with cardiology recommended within 30 days.', 'scheduling'),
    NegativeCase('Seen today at Riverside Family Medicine for a routine follow-up.', 'clinic_name'),
    NegativeCase('Referral placed to Lakeshore Cardiology Associates for further evaluation.', 'clinic_name'),
    NegativeCase("Records requested from Northgate Internal Medicine's prior visit.", 'clinic_name'),
    NegativeCase('Symptoms have been present for approximately two weeks.', 'duration'),
    NegativeCase('Patient reports the cough has persisted for five days.', 'duration'),
    NegativeCase('Pain has been intermittent over the past three months.', 'duration'),
    NegativeCase('Plan: continue current regimen, recheck labs in three months.', 'plan'),
    NegativeCase('Plan: physical therapy twice weekly for six weeks, then reassess.', 'plan'),
    NegativeCase('Plan: trial of dietary modification before adding medication.', 'plan'),
    NegativeCase('Colonoscopy performed without complication; three polyps removed.', 'procedure'),
    NegativeCase('EKG showed normal sinus rhythm, no acute ST changes.', 'procedure'),
    NegativeCase('Chest X-ray was clear, no infiltrate or effusion noted.', 'procedure'),
    NegativeCase("No known drug allergies reported at today's visit.", 'allergy'),
    NegativeCase('Allergic to penicillin; causes hives, noted in the chart.', 'allergy'),
    NegativeCase('Seasonal allergies to pollen, managed with antihistamines.', 'allergy'),
)

ALL_CATEGORIES = tuple(
    sorted({c.category for c in POSITIVE_CASES} | {c.category for c in NEGATIVE_CASES})
)
