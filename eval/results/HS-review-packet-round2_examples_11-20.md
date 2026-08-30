# HealthSteward Visit-Prep Review Packet — Round 2 — Examples 11-20

Thank you for taking about 30 minutes to review this. This is for a research paper evaluating an AI health-coordination tool called HealthSteward. All patient details below are **synthetic/fictional test data** — no real patient information is involved.

## What you're reviewing

HealthSteward generates "visit preparation" — a set of categorized questions and a short context summary — meant to help a patient prepare for an upcoming doctor's appointment, based on their medical history. Below are Examples 11-20 (10 examples), drawn from a stratified 30-case set spanning routine and adversarial patient scenarios across many specialties. Each includes a **full patient record** (exactly what the AI system had access to), then the AI-generated output, then a set of ratings to fill in.

For **Accuracy**, use the patient record as your ground truth: rate each category (and the context summary) separately. **Fully Supported** — every factual claim in this category (or the context summary) is stated in, or reasonably inferable from, the patient record. **Partially Supported** — at least one claim is unsupported, but not all. **Unsupported** — most/all claims are unsupported, OR any single claim would materially mislead the patient (e.g. a named external authority/guideline, or a specialty-management claim, not stated in the record). **N/A** — this category has no factual claims to check (purely open-ended/logistical questions).

---

## Example 11: routine_gastroenterology

*Routine gastroenterology follow-up for GERD on a PPI.*

**Patient record:**

- **Upcoming appointment:** GERD follow-up, Sep 2 2026, 9:00 AM, with Dr. Marcus Feld (Gastroenterology, Riverbend GI Associates)
- **Conditions:** Gastroesophageal Reflux Disease (active)
- **Medications:** Omeprazole 20mg once daily (prescribed by Dr. Marcus Feld, Gastroenterology, Riverbend GI Associates, for Acid suppression)
- **Lab orders:** none on file
- **Vitals:** none on file
- **Past visits:** none on file

**AI-generated output:**

**Condition Management**

- Are there any concerns about the effectiveness of omeprazole in managing my GERD symptoms?

**Medication Review**

- Is it possible to adjust the dosage of omeprazole to better manage my symptoms?

**Lab Results & Monitoring**

- Are there any pending lab tests or procedures scheduled for my follow-up visit?

**Lifestyle & Prevention**

- What lifestyle changes can I make to help manage my GERD symptoms, such as diet and exercise?
- Are there any specific foods or triggers that I should avoid to reduce my symptoms?

**Follow-up Planning**

- Is there a need for a follow-up appointment to monitor my symptoms or adjust my treatment plan?
- Are there any referrals or specialist appointments scheduled for my follow-up visit?

**Context summary shown to patient:** "The patient has an active diagnosis of GERD and is taking omeprazole for acid suppression. The purpose of the visit is to follow up on their symptoms and adjust their treatment plan as needed."

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

## Example 12: routine_psychiatry

*Routine psychiatry follow-up for major depressive disorder on an SSRI.*

**Patient record:**

- **Upcoming appointment:** Medication follow-up, Sep 1 2026, 10:00 AM, with Dr. Sam Okafor (Psychiatry, Lakeside Behavioral Health)
- **Conditions:** Major Depressive Disorder (active)
- **Medications:** Sertraline 100mg once daily (prescribed by Dr. Sam Okafor, Psychiatry, Lakeside Behavioral Health, for Depression management)
- **Lab orders:** none on file
- **Vitals:** none on file
- **Past visits:** none on file

**AI-generated output:**

**Condition Management**

- What are the expected symptoms of Major Depressive Disorder (F33.1) during the next 2 weeks, and how will they be monitored?
- Are there any changes to my current treatment plan for Major Depressive Disorder (F33.1) that I should be aware of?

**Medication Review**

- What are the potential side effects of Sertraline (100mg) that I should be aware of?
- Are there any dosage adjustments or changes to the treatment plan for Sertraline (100mg) that I should be aware of?

**Lab Results & Monitoring**

- What is the expected TSH level for someone with Major Depressive Disorder (F33.1) on Sertraline (100mg) treatment?
- Are there any pending lab results or tests that I should be aware of?

**Lifestyle & Prevention**

- How can I manage stress and anxiety while taking Sertraline (100mg) for Major Depressive Disorder (F33.1)?
- Are there any lifestyle changes or recommendations that can help improve my symptoms?

**Follow-up Planning**

- Is there a scheduled follow-up appointment for my medication follow-up on 2026-09-01T10:00:00?
- Are there any referrals or recommendations for additional treatment or support that I should be aware of?

**Context summary shown to patient:** "The patient has Major Depressive Disorder (F33.1) and is taking Sertraline (100mg) for depression management. The purpose of the upcoming appointment is a medication follow-up. The patient's current treatment plan and medication regimen will be discussed to ensure optimal management of their symptoms."

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

## Example 13: routine_orthopedics

*Routine orthopedics follow-up for knee osteoarthritis on an as-needed NSAID.*

**Patient record:**

- **Upcoming appointment:** Knee osteoarthritis follow-up, Sep 2 2026, 1:00 PM, with Dr. Foster Reyes (Orthopedics, Granite Orthopedic Group)
- **Conditions:** Osteoarthritis, Right Knee (active, mild)
- **Medications:** Naproxen 500mg as needed for pain (prescribed by Dr. Foster Reyes, Orthopedics, Granite Orthopedic Group, for Pain management)
- **Lab orders:** none on file
- **Vitals:** none on file
- **Past visits:** none on file

**AI-generated output:**

**Condition Management**

- What is the current severity of my right knee osteoarthritis, and are there any changes since our last visit?

**Medication Review**

- Are there any dosage adjustments or changes to my Naproxen regimen that I should be aware of?

**Lab Results & Monitoring**

- What are the latest lab results for my knee osteoarthritis, and are there any pending tests or follow-ups I should be aware of?

**Lifestyle & Prevention**

- Are there any lifestyle changes or recommendations I can make to help manage my knee osteoarthritis?

**Follow-up Planning**

- Is there a need for any further imaging or testing to monitor my knee osteoarthritis?
- Are there any referrals or specialists I should be seeing for my knee osteoarthritis?

**Context summary shown to patient:** "I have knee osteoarthritis and am taking Naproxen for pain management. I have a follow-up appointment with my Orthopedics specialist on 2026-09-02 to discuss my condition and treatment plan."

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

## Example 14: routine_ent

*Routine ENT follow-up for chronic sinusitis on a daily nasal spray.*

**Patient record:**

- **Upcoming appointment:** Chronic sinusitis follow-up, Sep 3 2026, 10:00 AM, with Dr. Marcus Webb (Otolaryngology, Bayshore ENT)
- **Conditions:** Chronic Sinusitis (active)
- **Medications:** Fluticasone Nasal Spray 50mcg/spray twice daily, both nostrils (prescribed by Dr. Marcus Webb, Otolaryngology, Bayshore ENT, for Sinus inflammation control)
- **Lab orders:** none on file
- **Vitals:** none on file
- **Past visits:** none on file

**AI-generated output:**

**Medication Review**

- Can I adjust the dosage or frequency of my fluticasone nasal spray, and if so, how often should I do so?

**Lifestyle & Prevention**

- Are there any lifestyle changes I can make to help manage my chronic sinusitis, such as avoiding allergens or using a humidifier?

**Follow-up Planning**

- Is there a need for further testing or evaluation, such as a CT scan or allergy testing, to better manage my chronic sinusitis?

**Context summary shown to patient:** "The patient has chronic sinusitis and is taking fluticasone nasal spray twice daily. The purpose of the visit is to follow up on the patient's condition and discuss any changes or concerns."

**Your ratings for this example:**

*Accuracy — rate EACH row below against the patient record above:*

- Medication Review: Fully Supported / Partially Supported / Unsupported / N/A — _______
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

## Example 15: labs_mixed_temporal_status

*Multiple lab orders at different ages, some recently ordered and some overdue for follow-up — tests whether temporal qualifiers are used correctly rather than presupposing results.*

**Patient record:**

- **Upcoming appointment:** IBD follow-up, Sep 4 2026, 11:00 AM, with Dr. Marcus Feld (Gastroenterology, Riverbend GI Associates)
- **Conditions:** Crohn's Disease (active)
- **Medications:** Mesalamine 1.2g three times daily (prescribed by Dr. Marcus Feld, Gastroenterology, Riverbend GI Associates, for Maintenance therapy)
- **Lab orders:** C-Reactive Protein, ordered 2026-08-25; Fecal Calprotectin, ordered 2026-03-01
- **Vitals:** none on file
- **Past visits:** none on file

**AI-generated output:**

**Condition Management**

- Are there any concerns about the effectiveness of my current treatment plan, and are there any potential side effects I should be aware of?

**Medication Review**

- Is there a need to adjust my dosage or frequency of taking mesalamine, and if so, what are the recommended changes?

**Lab Results & Monitoring**

- What are the results of my recent C-Reactive Protein test (ordered: 2026-08-25), and what do they indicate about my overall health?
- What are the results of my recent Fecal Calprotectin test (ordered: 2026-03-01), and how do they relate to my Crohn's Disease management?

**Lifestyle & Prevention**

- Are there any dietary changes or lifestyle modifications that I can make to help manage my Crohn's Disease?
- Are there any specific nutrients or supplements that I should be taking to support my treatment plan?

**Follow-up Planning**

- Is there a need for any additional testing or monitoring to support my treatment plan, and if so, what are the next steps?
- Are there any concerns about my upcoming appointment on 2026-09-04T11:00:00, and are there any specific topics that need to be discussed?

**Context summary shown to patient:** "The patient has active Crohn's Disease and is taking mesalamine for maintenance therapy. They have recent lab orders for C-Reactive Protein and Fecal Calprotectin, and their next appointment is scheduled for 2026-09-04T11:00:00."

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

## Example 16: same_specialty_switched_doctors

*Patient switched cardiologists; past visits exist with both the target doctor and a prior same-specialty doctor — tests same-doctor-only-most-recent handling in a non-unit-test case.*

**Patient record:**

- **Upcoming appointment:** Atrial fibrillation follow-up, Sep 4 2026, 1:00 PM, with Dr. Priya Nair (Cardiology, Harborview Cardiology)
- **Conditions:** Atrial Fibrillation (active)
- **Medications:** Apixaban 5mg twice daily (prescribed by Dr. Priya Nair, Cardiology, Harborview Cardiology, for Stroke prevention)
- **Lab orders:** none on file
- **Vitals:** none on file
- **Past visits:**
    - Jul 1 2026, 1:00 PM — AFib follow-up (with Dr. Priya Nair). Notes: "Rate well-controlled on current regimen."
    - Dec 1 2025, 1:00 PM — Initial AFib diagnosis (with Dr. Older Cardiologist). Notes: "Started on anticoagulation."

**AI-generated output:**

**Condition Management**

- What are the current rate control goals for my atrial fibrillation, and are they being met?
- Are there any changes to the recommended rate control strategy since my last visit?

**Medication Review**

- Is it possible to adjust the dosage of Apixaban to improve tolerability or reduce side effects?

**Lab Results & Monitoring**

- Are there any pending lab tests or procedures scheduled for my atrial fibrillation management?

**Lifestyle & Prevention**

- Are there any lifestyle modifications or recommendations that can help reduce my risk of stroke or improve my overall cardiovascular health?
- Should I consider any additional tests or screenings to monitor my atrial fibrillation or cardiovascular risk?

**Follow-up Planning**

- Is there a need for any further follow-up appointments or tests to monitor my atrial fibrillation?
- Are there any referrals or consultations with other specialists that I should be aware of?

**Context summary shown to patient:** "A 41-year-old patient with active atrial fibrillation, currently taking Apixaban for stroke prevention, is due for a follow-up appointment with their Cardiology specialist on 2026-09-04T13:00:00. The patient has a history of well-controlled atrial fibrillation on current regimen, but it is unclear if the current rate control strategy is optimal."

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

## Example 17: excluded_doctor_relevant_history

*A doctor with clearly relevant history is marked exclude_from_prep_context — checks that excluded context genuinely doesn't leak into the generated output.*

**Patient record:**

- **Upcoming appointment:** Thyroid follow-up, Sep 3 2026, 2:00 PM, with Dr. Elena Vance (Endocrinology, Bay Endocrinology)
- **Conditions:** Hashimoto's Thyroiditis (active)
- **Medications:** Levothyroxine 75mcg once daily, morning (prescribed by Dr. Elena Vance, Endocrinology, Bay Endocrinology, for Thyroid hormone replacement)
- **Lab orders:** none on file
- **Vitals:** none on file
- **Past visits:**
    - Jan 15 2026, 10:00 AM — Initial thyroid workup (with Dr. Old Provider). Notes: "Confidential note from prior provider — should not surface in visit-prep context."

**AI-generated output:**

**Condition Management**

- What are the current thyroid function test (TFT) results, and are there any adjustments needed to my Levothyroxine dosage?

**Medication Review**

- Can you review my Levothyroxine dosage and timing to ensure it's optimal for my Hashimoto's Thyroiditis?

**Lifestyle & Prevention**

- Are there any lifestyle changes I can make to help manage my Hashimoto's Thyroiditis, such as diet or exercise recommendations?

**Follow-up Planning**

- Is there a need for any follow-up appointments or tests in the near future?

**Context summary shown to patient:** "This patient has Hashimoto's Thyroiditis and is taking Levothyroxine for thyroid hormone replacement. The purpose of this visit is for a thyroid follow-up, and the patient's current medication regimen and lab results will be reviewed."

**Your ratings for this example:**

*Accuracy — rate EACH row below against the patient record above:*

- Condition Management: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Medication Review: Fully Supported / Partially Supported / Unsupported / N/A — _______
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

## Example 18: minimal_single_condition_single_med

*One condition, one medication, nothing else — a step above cold_start's zero-medication case, testing the floor with just barely enough data. Deliberately a different specialty/condition from any other case in this set (was previously a near-duplicate of routine_neurology's migraine/Topiramate profile — swapped to avoid overlapping coverage).*

**Patient record:**

- **Upcoming appointment:** Eczema follow-up, Sep 5 2026, 10:00 AM, with Dr. Priya Malhotra (Dermatology, Clearskin Dermatology)
- **Conditions:** Atopic Dermatitis (active)
- **Medications:** Tacrolimus Ointment 0.1% twice daily (prescribed by Dr. Priya Malhotra, Dermatology, Clearskin Dermatology, for Eczema flare control)
- **Lab orders:** none on file
- **Vitals:** none on file
- **Past visits:** none on file

**AI-generated output:**

**Condition Management**

- What are the current symptoms of my atopic dermatitis, and how can I manage them?
- Are there any changes in my condition that I should be aware of, and how can I track them?

**Medication Review**

- What are the potential side effects of Tacrolimus Ointment (0.1%) for my atopic dermatitis, and how can I minimize them?
- Are there any alternative treatments or medications that could be used for my condition, and why not?

**Lab Results & Monitoring**

- Are there any specific lab tests or examinations that I need to have to track my condition?

**Lifestyle & Prevention**

- How can I prevent eczema flare-ups, and what lifestyle changes can I make to reduce my symptoms?
- Are there any specific skin care routines or products that you recommend for my condition?

**Follow-up Planning**

- What are the next steps for my treatment plan, and when can I expect to see improvements in my symptoms?
- Are there any follow-up appointments or tests that I need to have to ensure my condition is being managed effectively?

**Context summary shown to patient:** "The patient has atopic dermatitis and is using Tacrolimus Ointment (0.1%) to manage their symptoms. They are due for a follow-up appointment with the Dermatology specialist on 2026-09-05T10:00:00 to discuss their condition and treatment plan."

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

## Example 19: cold_start

*Minimal profile: one condition, no medications, no past visits, no labs — exercises the fallback/format-validity path.*

**Patient record:**

- **Upcoming appointment:** Annual physical, Aug 3 2026, 9:00 AM, with Dr. Alex Kim (Family Medicine, Riverside Family Practice)
- **Conditions:** Seasonal Allergic Rhinitis (active)
- **Medications:** none on file
- **Lab orders:** none on file
- **Vitals:** none on file
- **Past visits:** none on file

**AI-generated output:**

**Lifestyle & Prevention**

- What lifestyle changes or recommendations can I make to help manage my Seasonal Allergic Rhinitis, such as avoiding triggers or using immunotherapy?

**Context summary shown to patient:** "The patient is scheduled for an annual physical with their Family Medicine specialist on August 3rd, 2026."

**Your ratings for this example:**

*Accuracy — rate EACH row below against the patient record above:*

- Lifestyle & Prevention: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Context Summary: Fully Supported / Partially Supported / Unsupported / N/A — _______

- **Relevance** (are the questions relevant to this patient's actual conditions, medications, and appointment purpose?): Relevant / Partially Relevant / Not Relevant — _______
- **Clarity** (are the questions clearly phrased and understandable to a patient, not overly clinical or confusing?): Clear / Partially Clear / Confusing — _______
- **Usefulness** (would bringing these questions to the appointment genuinely help the conversation with the doctor?): Useful / Partially Useful / Not Useful — _______
- **Missing category?** (given the patient record above, is there a category you'd expect to see that's missing entirely from the output?): None missing / Condition Management / Medication Review / Lab Results & Monitoring / Lifestyle & Prevention / Follow-up Planning / Other (note below) — _______
- **Would you personally bring this to an appointment, if it were your own visit?** Yes / No / Not sure — _______
- **Notes** (anything confusing, redundant, or that stood out, positively or negatively?): _______

---

## Example 20: tool_call_necessity_dosing

*Two same-specialty medications with a real absorption-timing interaction (mirrors docs/tdd.html's Walkthrough example) — get_medication_details is worth calling to answer this well.*

**Patient record:**

- **Upcoming appointment:** Diabetes and thyroid follow-up — reviewing medication timing, Aug 4 2026, 10:00 AM, with Dr. Elena Vance (Endocrinology, Bay Endocrinology)
- **Conditions:** Type 2 Diabetes Mellitus (active); Hashimoto's Thyroiditis (active)
- **Medications:** Metformin 500mg twice daily (prescribed by Dr. Elena Vance, Endocrinology, Bay Endocrinology, for Blood sugar control); Levothyroxine 75mcg once daily, morning (prescribed by Dr. Elena Vance, Endocrinology, Bay Endocrinology, for Thyroid hormone replacement)
- **Lab orders:** none on file
- **Vitals:** none on file
- **Past visits:** none on file

**AI-generated output:**

**Condition Management**

- What are the current blood sugar targets for my Type 2 Diabetes Mellitus, and are they being met?
- How does my Hashimoto's Thyroiditis affect my thyroid hormone levels, and what are the implications for my treatment plan?

**Medication Review**

- Are there any potential interactions between Metformin and Levothyroxine that I should be aware of?
- Can you confirm that the prescribed dosages of Metformin and Levothyroxine are the optimal starting points for my treatment plan?

**Lab Results & Monitoring**

- Are there any specific thyroid function tests that I should be monitoring, and what are the target ranges?

**Lifestyle & Prevention**

- What lifestyle changes can I make to improve my blood sugar control and thyroid function?
- Are there any specific dietary restrictions or recommendations for my Type 2 Diabetes Mellitus and Hashimoto's Thyroiditis?

**Follow-up Planning**

- Is there a need for any follow-up appointments or referrals to discuss my treatment plan?
- Are there any specific concerns or issues that need to be addressed before my next appointment?

**Context summary shown to patient:** "The patient has Type 2 Diabetes Mellitus and Hashimoto's Thyroiditis, and is taking Metformin and Levothyroxine. The purpose of the upcoming appointment is to review medication timing and discuss treatment plan."

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

## Overall (after all 10 examples)

Any general impressions of the tool's usefulness for patients navigating fragmented care across multiple specialists — including those managing multiple chronic conditions or systemic immune and hormonal comorbidities?

_______________________________________________

Thank you — this feedback goes directly into a research paper's evaluation section.