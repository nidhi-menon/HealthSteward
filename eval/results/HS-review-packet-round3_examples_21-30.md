# HealthSteward Visit-Prep Review Packet — Round 3 — Examples 21-30

Thank you for taking about 30 minutes to review this. This is for a research paper evaluating an AI health-coordination tool called HealthSteward. All patient details below are **synthetic/fictional test data** — no real patient information is involved.

## What you're reviewing

HealthSteward generates "visit preparation" — a set of categorized questions and a short context summary — meant to help a patient prepare for an upcoming doctor's appointment, based on their medical history. Below are Examples 21-30 (10 examples), drawn from a stratified 30-case set spanning routine and adversarial patient scenarios across many specialties. Each includes a **full patient record** (exactly what the AI system had access to), then the AI-generated output, then a set of ratings to fill in.

For **Accuracy**, use the patient record as your ground truth: rate each category (and the context summary) separately. **Fully Supported** — every factual claim in this category (or the context summary) is stated in, or reasonably inferable from, the patient record. **Partially Supported** — at least one claim is unsupported, but not all. **Unsupported** — most/all claims are unsupported, OR any single claim would materially mislead the patient (e.g. a named external authority/guideline, or a specialty-management claim, not stated in the record). **N/A** — this category has no factual claims to check (purely open-ended/logistical questions).

---

## Example 21: routine_nephrology

*Routine nephrology follow-up for stage 2 CKD on an ACE inhibitor.*

**Patient record:**

- **Upcoming appointment:** Chronic kidney disease follow-up, Sep 2 2026, 10:00 AM, with Dr. Ingrid Solberg (Nephrology, Meridian Kidney Care)
- **Conditions:** Chronic Kidney Disease, Stage 2 (active)
- **Medications:** Lisinopril 10mg once daily (prescribed by Dr. Ingrid Solberg, Nephrology, Meridian Kidney Care, for Blood pressure and renal protection)
- **Lab orders:** Basic Metabolic Panel (eGFR), ordered 2026-08-20
- **Vitals:** none on file
- **Past visits:** none on file

**AI-generated output:**

**Condition Management**

- What are the current kidney function estimates based on the eGFR test ordered on 2026-08-20?
- Are there any changes in the patient's kidney function since the last visit?

**Medication Review**

- Is there any need to adjust the dosage of Lisinopril based on the patient's current kidney function?

**Lab Results & Monitoring**

- What are the current estimated glomerular filtration rate (eGFR) values based on the recent test?
- Are there any pending lab tests or follow-up appointments related to the patient's kidney function?

**Lifestyle & Prevention**

- Are there any lifestyle modifications or dietary changes recommended for the patient's chronic kidney disease management?
- Are there any signs of worsening kidney function that the patient should be aware of?

**Follow-up Planning**

- Are there any referrals or specialist appointments scheduled for the patient's ongoing care?

**Context summary shown to patient:** "The patient has chronic kidney disease, stage 2, and is taking Lisinopril for blood pressure and renal protection. The patient's recent lab orders include a basic metabolic panel (eGFR) test ordered on 2026-08-20."

**Your ratings for this example:**

*Accuracy — rate EACH row below against the patient record above:*

- Condition Management: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Medication Review: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Lab Results & Monitoring: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Lifestyle & Prevention: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Follow-up Planning: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Context Summary: Fully Supported / Partially Supported / Unsupported / N/A — _______

- **Relevance** (are the questions relevant to this patient's actual conditions, medications, and appointment purpose?): Relevant / Partially Relevant / Not Relevant — _______
- **Clarity** (are the questions clearly phrased and understandable to a patient, not overly clinical or confusing?): Clear / Partially Clear / Confusing — _______
- **Usefulness** (would bringing these questions to the appointment genuinely help the conversation with the doctor?): Useful / Partially Useful / Not Useful — _______
- **Missing category?** (given the patient record above, is there a category you'd expect to see that's missing entirely from the output?): None missing / Condition Management / Medication Review / Lab Results & Monitoring / Lifestyle & Prevention / Follow-up Planning / Other (note below) — _______
- **Would you personally bring this to an appointment, if it were your own visit?** Yes / No / Not sure — _______
- **Notes** (anything confusing, redundant, or that stood out, positively or negatively?): _______

---

## Example 22: routine_obgyn

*Routine OB/GYN follow-up for PCOS on an oral contraceptive.*

**Patient record:**

- **Upcoming appointment:** PCOS follow-up, Sep 1 2026, 2:00 PM, with Dr. Renata Cruz (Obstetrics & Gynecology, Willowbrook Women's Health)
- **Conditions:** Polycystic Ovary Syndrome (active)
- **Medications:** Norethindrone/Ethinyl Estradiol 1mg/35mcg once daily (prescribed by Dr. Renata Cruz, Obstetrics & Gynecology, Willowbrook Women's Health, for Cycle regulation)
- **Lab orders:** none on file
- **Vitals:** none on file
- **Past visits:** none on file

**AI-generated output:**

**Condition Management**

- Are there any changes to my treatment plan for PCOS, and why?

**Medication Review**

- What are the potential side effects of Norethindrone/Ethinyl Estradiol, and how can I minimize them?

**Lab Results & Monitoring**

- Are there any additional lab tests that need to be run to monitor my PCOS symptoms or treatment response?

**Lifestyle & Prevention**

- What lifestyle changes can I make to help manage my PCOS symptoms and improve my overall health?
- Are there any specific dietary or exercise recommendations for me to follow?

**Follow-up Planning**

- What are the next steps in my care, and when can I expect to see my provider again?

**Context summary shown to patient:** "I am a 41-year-old woman with active Polycystic Ovary Syndrome (PCOS) and am taking Norethindrone/Ethinyl Estradiol for cycle regulation. I am due for a follow-up visit with my Obstetrics & Gynecology provider on September 1st, 2026."

**Your ratings for this example:**

*Accuracy — rate EACH row below against the patient record above:*

- Condition Management: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Medication Review: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Lab Results & Monitoring: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Lifestyle & Prevention: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Follow-up Planning: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Context Summary: Fully Supported / Partially Supported / Unsupported / N/A — _______

- **Relevance** (are the questions relevant to this patient's actual conditions, medications, and appointment purpose?): Relevant / Partially Relevant / Not Relevant — _______
- **Clarity** (are the questions clearly phrased and understandable to a patient, not overly clinical or confusing?): Clear / Partially Clear / Confusing — _______
- **Usefulness** (would bringing these questions to the appointment genuinely help the conversation with the doctor?): Useful / Partially Useful / Not Useful — _______
- **Missing category?** (given the patient record above, is there a category you'd expect to see that's missing entirely from the output?): None missing / Condition Management / Medication Review / Lab Results & Monitoring / Lifestyle & Prevention / Follow-up Planning / Other (note below) — _______
- **Would you personally bring this to an appointment, if it were your own visit?** Yes / No / Not sure — _______
- **Notes** (anything confusing, redundant, or that stood out, positively or negatively?): _______

---

## Example 23: routine_ophthalmology

*Routine ophthalmology follow-up for glaucoma on daily eye drops.*

**Patient record:**

- **Upcoming appointment:** Glaucoma follow-up, Sep 3 2026, 9:00 AM, with Dr. Nadia Petrov (Ophthalmology, Clearview Eye Institute)
- **Conditions:** Primary Open-Angle Glaucoma (active)
- **Medications:** Latanoprost 0.005% once daily at bedtime, both eyes (prescribed by Dr. Nadia Petrov, Ophthalmology, Clearview Eye Institute, for Intraocular pressure control)
- **Lab orders:** none on file
- **Vitals:** none on file
- **Past visits:** none on file

**AI-generated output:**

**Condition Management**

- What are the current intraocular pressure readings, and are they within the target range for my glaucoma treatment?
- Are there any changes in my glaucoma management plan, such as adjustments to my medication regimen or follow-up schedule?

**Medication Review**

- Is it necessary to adjust my latanoprost dosage or timing, and if so, what are the recommended changes?

**Lab Results & Monitoring**

- Are there any pending lab tests or examinations that I need to have, and if so, what are the scheduled dates?

**Lifestyle & Prevention**

- Are there any lifestyle changes I can make to help manage my glaucoma, such as diet or exercise recommendations?
- Are there any specific eye care habits I should follow to help prevent further progression of my glaucoma?

**Follow-up Planning**

- Is there a need for a follow-up appointment within the next few months, and if so, what are the scheduled dates and times?
- Are there any referrals or specialist appointments that I need to schedule in the near future?

**Context summary shown to patient:** "The patient has primary open-angle glaucoma and is taking latanoprost to control intraocular pressure. They have an upcoming appointment with their Ophthalmology to discuss their glaucoma management plan and any necessary adjustments."

**Your ratings for this example:**

*Accuracy — rate EACH row below against the patient record above:*

- Condition Management: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Medication Review: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Lab Results & Monitoring: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Lifestyle & Prevention: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Follow-up Planning: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Context Summary: Fully Supported / Partially Supported / Unsupported / N/A — _______

- **Relevance** (are the questions relevant to this patient's actual conditions, medications, and appointment purpose?): Relevant / Partially Relevant / Not Relevant — _______
- **Clarity** (are the questions clearly phrased and understandable to a patient, not overly clinical or confusing?): Clear / Partially Clear / Confusing — _______
- **Usefulness** (would bringing these questions to the appointment genuinely help the conversation with the doctor?): Useful / Partially Useful / Not Useful — _______
- **Missing category?** (given the patient record above, is there a category you'd expect to see that's missing entirely from the output?): None missing / Condition Management / Medication Review / Lab Results & Monitoring / Lifestyle & Prevention / Follow-up Planning / Other (note below) — _______
- **Would you personally bring this to an appointment, if it were your own visit?** Yes / No / Not sure — _______
- **Notes** (anything confusing, redundant, or that stood out, positively or negatively?): _______

---

## Example 24: routine_cardiology

*Routine cardiology follow-up for atrial fibrillation on anticoagulation.*

**Patient record:**

- **Upcoming appointment:** Atrial fibrillation follow-up, Sep 1 2026, 9:00 AM, with Dr. Priya Nair (Cardiology, Harborview Cardiology)
- **Conditions:** Atrial Fibrillation (active)
- **Medications:** Apixaban 5mg twice daily (prescribed by Dr. Priya Nair, Cardiology, Harborview Cardiology, for Stroke prevention); Metoprolol 25mg twice daily (prescribed by Dr. Priya Nair, Cardiology, Harborview Cardiology, for Rate control)
- **Lab orders:** none on file
- **Vitals:** none on file
- **Past visits:** none on file

**AI-generated output:**

**Condition Management**

- Are there any concerns about the risk of stroke or embolism with Apixaban, and are there any alternative anticoagulants being considered?
- How is the rate control with Metoprolol, and are there any adjustments that need to be made?

**Medication Review**

- Are there any potential interactions between Apixaban and Metoprolol that I should be aware of?
- Are there any changes to the dosing schedule for either medication that I should be aware of?
- Are there any alternative medications that could be used to manage my atrial fibrillation?

**Lab Results & Monitoring**

- What are the latest results for my INR level, and are there any adjustments that need to be made to my Apixaban dosage?
- Are there any pending lab tests or monitoring that I should be aware of?

**Lifestyle & Prevention**

- Are there any lifestyle changes that I can make to reduce my risk of stroke or heart failure?
- Are there any recommendations for exercise or physical activity that I should follow?

**Follow-up Planning**

- Is there a need for a follow-up appointment in the near future?
- Are there any referrals or specialist appointments that I need to schedule?

**Context summary shown to patient:** (none generated for this example)

**Your ratings for this example:**

*Accuracy — rate EACH row below against the patient record above:*

- Condition Management: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Medication Review: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Lab Results & Monitoring: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Lifestyle & Prevention: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Follow-up Planning: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Context Summary: Fully Supported / Partially Supported / Unsupported / N/A — _______

- **Relevance** (are the questions relevant to this patient's actual conditions, medications, and appointment purpose?): Relevant / Partially Relevant / Not Relevant — _______
- **Clarity** (are the questions clearly phrased and understandable to a patient, not overly clinical or confusing?): Clear / Partially Clear / Confusing — _______
- **Usefulness** (would bringing these questions to the appointment genuinely help the conversation with the doctor?): Useful / Partially Useful / Not Useful — _______
- **Missing category?** (given the patient record above, is there a category you'd expect to see that's missing entirely from the output?): None missing / Condition Management / Medication Review / Lab Results & Monitoring / Lifestyle & Prevention / Follow-up Planning / Other (note below) — _______
- **Would you personally bring this to an appointment, if it were your own visit?** Yes / No / Not sure — _______
- **Notes** (anything confusing, redundant, or that stood out, positively or negatively?): _______

---

## Example 25: condition_severity_variation

*A condition explicitly marked severe — tests whether severity influences question specificity without inventing facts beyond what the severity field states.*

**Patient record:**

- **Upcoming appointment:** Severe asthma follow-up, Sep 4 2026, 2:00 PM, with Dr. Owen Baptiste (Pulmonology, Summit Pulmonary Care)
- **Conditions:** Asthma (active, severe)
- **Medications:** Fluticasone/Salmeterol 500/50mcg twice daily (prescribed by Dr. Owen Baptiste, Pulmonology, Summit Pulmonary Care, for Asthma maintenance); Albuterol 90mcg as needed (prescribed by Dr. Owen Baptiste, Pulmonology, Summit Pulmonary Care, for Rescue inhaler)
- **Lab orders:** none on file
- **Vitals:** none on file
- **Past visits:** none on file

**AI-generated output:**

**Condition Management**

- What is the current severity of my asthma, and how does it compare to my previous visits?
- What are the specific triggers that are causing my asthma to be severe, and how can I avoid them?

**Medication Review**

- Are there any adjustments that need to be made to my Fluticasone/Salmeterol dosage, and why?
- Are there any potential interactions between my Fluticasone/Salmeterol and Albuterol that I should be aware of?

**Lab Results & Monitoring**

- What are my latest lung function test results, and how do they compare to my previous tests?
- Are there any pending lab tests that I need to have done, and what are their purposes?

**Lifestyle & Prevention**

- What lifestyle changes can I make to help manage my asthma, and how often should I monitor my symptoms?
- Are there any specific asthma-friendly products or services that you recommend?

**Follow-up Planning**

- Is there a need for any additional testing or follow-up appointments in the next few months?
- Are there any referrals or specialist appointments that I need to schedule in the near future?

**Context summary shown to patient:** (none generated for this example)

**Your ratings for this example:**

*Accuracy — rate EACH row below against the patient record above:*

- Condition Management: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Medication Review: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Lab Results & Monitoring: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Lifestyle & Prevention: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Follow-up Planning: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Context Summary: Fully Supported / Partially Supported / Unsupported / N/A — _______

- **Relevance** (are the questions relevant to this patient's actual conditions, medications, and appointment purpose?): Relevant / Partially Relevant / Not Relevant — _______
- **Clarity** (are the questions clearly phrased and understandable to a patient, not overly clinical or confusing?): Clear / Partially Clear / Confusing — _______
- **Usefulness** (would bringing these questions to the appointment genuinely help the conversation with the doctor?): Useful / Partially Useful / Not Useful — _______
- **Missing category?** (given the patient record above, is there a category you'd expect to see that's missing entirely from the output?): None missing / Condition Management / Medication Review / Lab Results & Monitoring / Lifestyle & Prevention / Follow-up Planning / Other (note below) — _______
- **Would you personally bring this to an appointment, if it were your own visit?** Yes / No / Not sure — _______
- **Notes** (anything confusing, redundant, or that stood out, positively or negatively?): _______

---

## Example 26: referral_carryover_unconfirmed

*A past visit's notes mention a planned referral; the next visit's notes are silent on it — a real carryover the model should surface as a follow-up question.*

**Patient record:**

- **Upcoming appointment:** CKD follow-up, Sep 4 2026, 10:00 AM, with Dr. Ingrid Solberg (Nephrology, Meridian Kidney Care)
- **Conditions:** Chronic Kidney Disease, Stage 3 (active)
- **Medications:** Lisinopril 10mg once daily (prescribed by Dr. Ingrid Solberg, Nephrology, Meridian Kidney Care, for Blood pressure and renal protection)
- **Lab orders:** none on file
- **Vitals:** none on file
- **Past visits:**
    - Jul 15 2026, 10:00 AM — CKD follow-up (with Dr. Ingrid Solberg). Notes: "eGFR stable. Discussed hydration and blood pressure control."
    - Jun 1 2026, 10:00 AM — CKD follow-up (with Dr. Ingrid Solberg). Notes: "Planned to discuss: referral to a renal dietitian for dietary management."

**AI-generated output:**

**Condition Management**

- What are the current kidney function tests (eGFR) and how do they compare to the previous visit?
- Are there any changes to my CKD stage or classification?
- What are the current treatment goals for my CKD, and how will they be monitored?

**Medication Review**

- Is there any need to adjust the dosage of Lisinopril, and what are the potential benefits and risks of changing the medication?

**Lab Results & Monitoring**

- What are the current lab results for my kidney function, and when can I expect to see the next set of results?
- Are there any pending lab tests or procedures that I should be aware of?

**Lifestyle & Prevention**

- What dietary changes can I make to better manage my CKD, and how can I work with a renal dietitian to develop a personalized plan?
- Are there any lifestyle modifications I can make to reduce my risk of CKD progression?

**Follow-up Planning**

- Is there a need for a referral to a renal dietitian, and when can I expect to see a specialist?
- Are there any upcoming appointments or procedures that I should be aware of?

**Context summary shown to patient:** "The patient has Chronic Kidney Disease, Stage 3, and is currently taking Lisinopril for blood pressure and renal protection. The patient's last CKD follow-up visit was on 2026-07-15T10:00:00, and the provider discussed hydration and blood pressure control. The patient is due for a follow-up visit on 2026-09-04T10:00:00."

**Your ratings for this example:**

*Accuracy — rate EACH row below against the patient record above:*

- Condition Management: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Medication Review: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Lab Results & Monitoring: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Lifestyle & Prevention: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Follow-up Planning: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Context Summary: Fully Supported / Partially Supported / Unsupported / N/A — _______

- **Relevance** (are the questions relevant to this patient's actual conditions, medications, and appointment purpose?): Relevant / Partially Relevant / Not Relevant — _______
- **Clarity** (are the questions clearly phrased and understandable to a patient, not overly clinical or confusing?): Clear / Partially Clear / Confusing — _______
- **Usefulness** (would bringing these questions to the appointment genuinely help the conversation with the doctor?): Useful / Partially Useful / Not Useful — _______
- **Missing category?** (given the patient record above, is there a category you'd expect to see that's missing entirely from the output?): None missing / Condition Management / Medication Review / Lab Results & Monitoring / Lifestyle & Prevention / Follow-up Planning / Other (note below) — _______
- **Would you personally bring this to an appointment, if it were your own visit?** Yes / No / Not sure — _______
- **Notes** (anything confusing, redundant, or that stood out, positively or negatively?): _______

---

## Example 27: all_out_of_scope_for_specialty

*Every condition and medication is out of scope for the target specialty — an extreme version of cross_specialty_scope. Every category should legitimately have little or nothing to say; tests whether the model produces a short, honest list instead of padding with off-scope or invented content.*

**Patient record:**

- **Upcoming appointment:** Annual eye exam, Sep 5 2026, 2:00 PM, with Dr. Nadia Petrov (Ophthalmology, Clearview Eye Institute)
- **Conditions:** Mild Plaque Psoriasis (active, unrelated to today's visit); Essential Hypertension (active, unrelated to today's visit)
- **Medications:** Clobetasol Cream 0.05% once daily (prescribed by Dr. Rita Fields, Dermatology, Clearskin Dermatology, for Psoriasis flare control); Amlodipine 5mg once daily (prescribed by Dr. Alex Kim, Family Medicine, Riverside Family Practice, for Blood pressure control)
- **Lab orders:** none on file
- **Vitals:** none on file
- **Past visits:** none on file

**AI-generated output:**

**Condition Management**

- Are there any new or worsening symptoms of Essential Hypertension that need to be addressed?
- Are there any changes to my treatment plan for either condition that I should be aware of?

**Medication Review**

- What are the potential interactions between Clobetasol Cream (0.05%) and Amlodipine (5mg) that I should be aware of?
- Are there any alternative treatments for my Psoriasis that could reduce the risk of side effects from Clobetasol Cream?
- Can you review my Amlodipine (5mg) dosage and schedule to ensure it is aligned with my blood pressure control goals?

**Lab Results & Monitoring**

- What are the expected results for my upcoming eye exam, and are there any specific tests or screenings that I need to be aware of?
- Are there any changes to my eye exam schedule or procedures that I should be aware of?
- What are the current guidelines for monitoring my eye health as it relates to my Plaque Psoriasis and Essential Hypertension?

**Lifestyle & Prevention**

- Are there any lifestyle changes or recommendations that I can make to reduce my risk of eye problems related to my Plaque Psoriasis?
- Can you provide guidance on how to manage stress and anxiety, which can exacerbate my Plaque Psoriasis?
- Are there any specific eye care habits or routines that you recommend for someone with my medical conditions?

**Follow-up Planning**

- Is there a need for any follow-up appointments or tests in the near future?
- Are there any referrals or specialist appointments that I need to schedule?
- Is there a carryover concern from my last visit's planned-but-unconfirmed-as-addressed topics that I should be aware of?

**Context summary shown to patient:** "The patient is scheduled for an annual eye exam at Clearview Eye Institute on 2026-09-05T14:00:00. They have mild Plaque Psoriasis and Essential Hypertension, and are currently taking Clobetasol Cream (0.05%) and Amlodipine (5mg). The patient should be aware of potential interactions between their medications, and should discuss any changes to their treatment plan or lifestyle habits with their ophthalmologist."

**Your ratings for this example:**

*Accuracy — rate EACH row below against the patient record above:*

- Condition Management: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Medication Review: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Lab Results & Monitoring: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Lifestyle & Prevention: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Follow-up Planning: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Context Summary: Fully Supported / Partially Supported / Unsupported / N/A — _______

- **Relevance** (are the questions relevant to this patient's actual conditions, medications, and appointment purpose?): Relevant / Partially Relevant / Not Relevant — _______
- **Clarity** (are the questions clearly phrased and understandable to a patient, not overly clinical or confusing?): Clear / Partially Clear / Confusing — _______
- **Usefulness** (would bringing these questions to the appointment genuinely help the conversation with the doctor?): Useful / Partially Useful / Not Useful — _______
- **Missing category?** (given the patient record above, is there a category you'd expect to see that's missing entirely from the output?): None missing / Condition Management / Medication Review / Lab Results & Monitoring / Lifestyle & Prevention / Follow-up Planning / Other (note below) — _______
- **Would you personally bring this to an appointment, if it were your own visit?** Yes / No / Not sure — _______
- **Notes** (anything confusing, redundant, or that stood out, positively or negatively?): _______

---

## Example 28: many_irrelevant_past_visits

*Several past visits, all with an unrelated-specialty doctor — tests retrieval filtering under volume, distinct from retrieval_redundancy's same-doctor case. Deliberately a different specialty/condition from any other case in this set (was previously a near-duplicate of routine_ophthalmology's glaucoma/Latanoprost profile — swapped to avoid overlapping coverage).*

**Patient record:**

- **Upcoming appointment:** Benign prostatic hyperplasia follow-up, Sep 5 2026, 11:00 AM, with Dr. Victor Amado (Urology, Meridian Urology Associates)
- **Conditions:** Benign Prostatic Hyperplasia (active)
- **Medications:** Tamsulosin 0.4mg once daily (prescribed by Dr. Victor Amado, Urology, Meridian Urology Associates, for Urinary symptom control)
- **Lab orders:** none on file
- **Vitals:** none on file
- **Past visits:**
    - Jun 1 2026, 11:00 AM — Acne follow-up (with Dr. Rita Fields). Notes: "Improved with current regimen."
    - Mar 1 2026, 11:00 AM — Acne follow-up (with Dr. Rita Fields). Notes: "Started topical retinoid."
    - Dec 1 2025, 11:00 AM — New patient dermatology visit (with Dr. Rita Fields). Notes: "Initial acne assessment."

**AI-generated output:**

**Condition Management**

- Are there any concerns about the potential for tamsulosin to cause ejaculatory dysfunction or other side effects?

**Medication Review**

- Is there a need to adjust the dosage of tamsulosin, and if so, what are the recommended changes?

**Lab Results & Monitoring**

- Are there any other lab results or monitoring that I should be aware of in relation to my BPH?

**Lifestyle & Prevention**

- Are there any lifestyle changes that I can make to help manage my BPH symptoms?
- Are there any recommendations for maintaining a healthy prostate through diet and exercise?

**Follow-up Planning**

- Is there a need for a repeat PSA test or any other follow-up testing in the near future?
- Are there any upcoming appointments or procedures scheduled for my BPH care?

**Context summary shown to patient:** "The patient has an active diagnosis of benign prostatic hyperplasia and is taking tamsulosin for urinary symptom control. The purpose of the upcoming appointment is to follow up on the patient's condition and discuss any changes or concerns."

**Your ratings for this example:**

*Accuracy — rate EACH row below against the patient record above:*

- Condition Management: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Medication Review: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Lab Results & Monitoring: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Lifestyle & Prevention: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Follow-up Planning: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Context Summary: Fully Supported / Partially Supported / Unsupported / N/A — _______

- **Relevance** (are the questions relevant to this patient's actual conditions, medications, and appointment purpose?): Relevant / Partially Relevant / Not Relevant — _______
- **Clarity** (are the questions clearly phrased and understandable to a patient, not overly clinical or confusing?): Clear / Partially Clear / Confusing — _______
- **Usefulness** (would bringing these questions to the appointment genuinely help the conversation with the doctor?): Useful / Partially Useful / Not Useful — _______
- **Missing category?** (given the patient record above, is there a category you'd expect to see that's missing entirely from the output?): None missing / Condition Management / Medication Review / Lab Results & Monitoring / Lifestyle & Prevention / Follow-up Planning / Other (note below) — _______
- **Would you personally bring this to an appointment, if it were your own visit?** Yes / No / Not sure — _______
- **Notes** (anything confusing, redundant, or that stood out, positively or negatively?): _______

---

## Example 29: cross_specialty_scope

*Endocrinology visit; patient also has a dermatology medication from an unrelated doctor — scope checker should catch a question about it if the model generates one.*

**Patient record:**

- **Upcoming appointment:** Diabetes follow-up, Aug 1 2026, 10:00 AM, with Dr. Elena Vance (Endocrinology, Bay Endocrinology)
- **Conditions:** Type 2 Diabetes Mellitus (active); Mild Plaque Psoriasis (active, unrelated to today's visit)
- **Medications:** Metformin 500mg twice daily (prescribed by Dr. Elena Vance, Endocrinology, Bay Endocrinology, for Blood sugar control); Clobetasol Cream 0.05% once daily (prescribed by Dr. Rita Fields, Dermatology, Clearskin Dermatology, for Psoriasis flare control)
- **Lab orders:** none on file
- **Vitals:** none on file
- **Past visits:** none on file

**AI-generated output:**

**Condition Management**

- What are the current blood sugar targets for my Type 2 Diabetes Mellitus, and are they being met?
- Are there any changes to my medication regimen or dosage schedule that I should be aware of?
- What are the next steps for managing my Type 2 Diabetes Mellitus, and are there any new tests or monitoring requirements?

**Medication Review**

- Are there any potential interactions between Metformin and Clobetasol Cream that I should be aware of?
- Can I adjust my Metformin dosage or timing to better manage my blood sugar levels?
- Are there any alternative medications or treatments that could be more effective for my Type 2 Diabetes Mellitus?

**Lab Results & Monitoring**

- Are there any pending lab tests or monitoring requirements that I should be aware of?

**Lifestyle & Prevention**

- What lifestyle changes can I make to better manage my Type 2 Diabetes Mellitus and prevent complications?
- Are there any specific dietary or exercise recommendations for my condition?

**Follow-up Planning**

- Are there any pending referrals or tests that need to be scheduled?

**Context summary shown to patient:** (none generated for this example)

**Your ratings for this example:**

*Accuracy — rate EACH row below against the patient record above:*

- Condition Management: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Medication Review: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Lab Results & Monitoring: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Lifestyle & Prevention: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Follow-up Planning: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Context Summary: Fully Supported / Partially Supported / Unsupported / N/A — _______

- **Relevance** (are the questions relevant to this patient's actual conditions, medications, and appointment purpose?): Relevant / Partially Relevant / Not Relevant — _______
- **Clarity** (are the questions clearly phrased and understandable to a patient, not overly clinical or confusing?): Clear / Partially Clear / Confusing — _______
- **Usefulness** (would bringing these questions to the appointment genuinely help the conversation with the doctor?): Useful / Partially Useful / Not Useful — _______
- **Missing category?** (given the patient record above, is there a category you'd expect to see that's missing entirely from the output?): None missing / Condition Management / Medication Review / Lab Results & Monitoring / Lifestyle & Prevention / Follow-up Planning / Other (note below) — _______
- **Would you personally bring this to an appointment, if it were your own visit?** Yes / No / Not sure — _______
- **Notes** (anything confusing, redundant, or that stood out, positively or negatively?): _______

---

## Example 30: retrieval_redundancy

*Several past visits with the target doctor, already surfaced by Phase 1 context selection — if the model calls lookup_past_visits, check whether it just re-fetched what Phase 1 already provided.*

**Patient record:**

- **Upcoming appointment:** Reviewing thyroid management history and recent lab trends, Aug 5 2026, 10:00 AM, with Dr. Elena Vance (Endocrinology, Bay Endocrinology)
- **Conditions:** Hashimoto's Thyroiditis (active)
- **Medications:** Levothyroxine 75mcg once daily, morning (prescribed by Dr. Elena Vance, Endocrinology, Bay Endocrinology, for Thyroid hormone replacement)
- **Lab orders:** none on file
- **Vitals:** none on file
- **Past visits:**
    - May 1 2026, 10:00 AM — Thyroid follow-up (with Dr. Elena Vance). Notes: "TSH trending down, dose unchanged."
    - Feb 1 2026, 10:00 AM — Thyroid follow-up (with Dr. Elena Vance). Notes: "Increased Levothyroxine to 75mcg."
    - Nov 1 2025, 10:00 AM — Initial Hashimoto's diagnosis (with Dr. Elena Vance). Notes: "Started Levothyroxine 50mcg."

**AI-generated output:**

**Lab Results & Monitoring**

- Are there any pending lab tests or follow-up appointments that need to be discussed?

**Lifestyle & Prevention**

- Are there any lifestyle modifications that can be recommended to help manage Hashimoto's Thyroiditis symptoms, such as dietary changes or stress management techniques?

**Follow-up Planning**

- Are there any referrals or specialist appointments that need to be scheduled for the patient's Hashimoto's Thyroiditis management?

**Context summary shown to patient:** "The patient has Hashimoto's Thyroiditis and is taking Levothyroxine for thyroid hormone replacement. The upcoming appointment is to review the patient's thyroid management history and recent lab trends."

**Your ratings for this example:**

*Accuracy — rate EACH row below against the patient record above:*

- Lab Results & Monitoring: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Lifestyle & Prevention: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Follow-up Planning: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Context Summary: Fully Supported / Partially Supported / Unsupported / N/A — _______

- **Relevance** (are the questions relevant to this patient's actual conditions, medications, and appointment purpose?): Relevant / Partially Relevant / Not Relevant — _______
- **Clarity** (are the questions clearly phrased and understandable to a patient, not overly clinical or confusing?): Clear / Partially Clear / Confusing — _______
- **Usefulness** (would bringing these questions to the appointment genuinely help the conversation with the doctor?): Useful / Partially Useful / Not Useful — _______
- **Missing category?** (given the patient record above, is there a category you'd expect to see that's missing entirely from the output?): None missing / Condition Management / Medication Review / Lab Results & Monitoring / Lifestyle & Prevention / Follow-up Planning / Other (note below) — _______
- **Would you personally bring this to an appointment, if it were your own visit?** Yes / No / Not sure — _______
- **Notes** (anything confusing, redundant, or that stood out, positively or negatively?): _______

---

## Overall (after all 10 examples)

Any general impressions of the tool's usefulness for patients navigating fragmented care across multiple specialists — including those managing multiple chronic conditions or systemic immune and hormonal comorbidities?

_______________________________________________

Thank you — this feedback goes directly into a research paper's evaluation section.