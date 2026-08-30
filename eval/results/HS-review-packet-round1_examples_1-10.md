# HealthSteward Visit-Prep Review Packet — Round 1 — Examples 1-10

Thank you for taking about 30 minutes to review this. This is for a research paper evaluating an AI health-coordination tool called HealthSteward. All patient details below are **synthetic/fictional test data** — no real patient information is involved.

## What you're reviewing

HealthSteward generates "visit preparation" — a set of categorized questions and a short context summary — meant to help a patient prepare for an upcoming doctor's appointment, based on their medical history. Below are Examples 1-10 (10 examples), drawn from a stratified 30-case set spanning routine and adversarial patient scenarios across many specialties. Each includes a **full patient record** (exactly what the AI system had access to), then the AI-generated output, then a set of ratings to fill in.

For **Accuracy**, use the patient record as your ground truth: rate each category (and the context summary) separately. **Fully Supported** — every factual claim in this category (or the context summary) is stated in, or reasonably inferable from, the patient record. **Partially Supported** — at least one claim is unsupported, but not all. **Unsupported** — most/all claims are unsupported, OR any single claim would materially mislead the patient (e.g. a named external authority/guideline, or a specialty-management claim, not stated in the record). **N/A** — this category has no factual claims to check (purely open-ended/logistical questions).

---

## Example 1: routine_neurology

*Routine neurology follow-up for migraine on a preventive medication.*

**Patient record:**

- **Upcoming appointment:** Migraine follow-up, Sep 2 2026, 2:00 PM, with Dr. Beatrice Lund (Neurology, Cedar Neurology Clinic)
- **Conditions:** Chronic Migraine (active)
- **Medications:** Topiramate 50mg twice daily (prescribed by Dr. Beatrice Lund, Neurology, Cedar Neurology Clinic, for Migraine prevention)
- **Lab orders:** none on file
- **Vitals:** none on file
- **Past visits:** none on file

**AI-generated output:**

**Condition Management**

- Are there any adjustments to be made to my current treatment plan for chronic migraines?

**Medication Review**

- What are the potential side effects of Topiramate, and how can I minimize them?
- Are there any dosage adjustments that can be made to Topiramate to better manage my migraines?

**Lab Results & Monitoring**

- What are the next steps for monitoring my migraine frequency and severity?
- Are there any additional lab tests that need to be run to track my condition?

**Lifestyle & Prevention**

- What lifestyle changes can I make to help reduce my migraine frequency and severity?
- Are there any specific dietary or exercise recommendations for managing chronic migraines?

**Follow-up Planning**

- Is there a need for a follow-up appointment in the near future?
- Are there any referrals or specialist appointments that need to be scheduled?

**Context summary shown to patient:** "The patient has chronic migraines and is taking Topiramate for migraine prevention. The purpose of the visit is to follow up on their current treatment plan and make any necessary adjustments."

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

## Example 2: routine_pulmonology

*Routine pulmonology follow-up for asthma on a maintenance inhaler.*

**Patient record:**

- **Upcoming appointment:** Asthma follow-up, Sep 1 2026, 1:00 PM, with Dr. Owen Baptiste (Pulmonology, Summit Pulmonary Care)
- **Conditions:** Asthma (active)
- **Medications:** Fluticasone/Salmeterol 250/50mcg twice daily (prescribed by Dr. Owen Baptiste, Pulmonology, Summit Pulmonary Care, for Asthma maintenance)
- **Lab orders:** none on file
- **Vitals:** none on file
- **Past visits:** none on file

**AI-generated output:**

**Condition Management**

- What are the current asthma symptoms, and how have they been managing over the past few months?
- Are there any changes in my asthma medication regimen that I should be aware of?

**Medication Review**

- What is the purpose of my current medication regimen, and how will it be adjusted if necessary?
- Are there any potential interactions between my medications and other health conditions I may have?

**Lab Results & Monitoring**

- What are my current lung function test results (e.g., FEV1), and are there any changes or concerns?
- Are there any pending lab tests or monitoring that I should be aware of?

**Lifestyle & Prevention**

- What lifestyle changes can I make to better manage my asthma, and how often should I monitor my symptoms?
- Are there any specific allergens or triggers that I should avoid or take precautions against?

**Follow-up Planning**

- What is the plan for my next follow-up appointment, and are there any specific topics to be discussed?
- Are there any referrals or specialist appointments that I need to schedule in the near future?

**Context summary shown to patient:** "As we prepare for your asthma follow-up appointment, I want to ensure that we review your current symptoms, medication regimen, and any changes or concerns. This will help us tailor a plan to better manage your asthma and prevent any potential complications."

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

## Example 3: routine_family_medicine_multicondition

*Routine PCP follow-up for hypertension and hyperlipidemia, two conditions and two meds.*

**Patient record:**

- **Upcoming appointment:** Hypertension and cholesterol follow-up, Sep 2 2026, 11:00 AM, with Dr. Alex Kim (Family Medicine, Riverside Family Practice)
- **Conditions:** Essential Hypertension (active); Hyperlipidemia (active)
- **Medications:** Amlodipine 5mg once daily (prescribed by Dr. Alex Kim, Family Medicine, Riverside Family Practice, for Blood pressure control); Atorvastatin 20mg once daily at bedtime (prescribed by Dr. Alex Kim, Family Medicine, Riverside Family Practice, for Cholesterol management)
- **Lab orders:** none on file
- **Vitals:** none on file
- **Past visits:** none on file

**AI-generated output:**

**Condition Management**

- What is the current blood pressure reading, and are there any concerns regarding my hypertension management?
- Are there any changes to my cholesterol management plan, and what are the updated lipid profiles?

**Medication Review**

- Are there any potential interactions between my Amlodipine and Atorvastatin that I should be aware of?
- Is there a need to adjust the dosage or timing of my medications?

**Lab Results & Monitoring**

- What are the latest lipid profiles, and are there any concerns regarding my cholesterol levels?
- Are there any pending lab results that I should be aware of?

**Lifestyle & Prevention**

- What lifestyle changes can I make to improve my blood pressure and cholesterol management?
- Are there any recommendations for diet, exercise, or stress management?

**Follow-up Planning**

- Are there any referrals or next steps that I should be aware of?

**Context summary shown to patient:** "The patient has essential hypertension and hyperlipidemia, and is due for a follow-up appointment with their Family Medicine specialist to discuss their management plans. The patient is currently taking Amlodipine and Atorvastatin, and has not had any recent lab results or follow-up appointments with Cardiology."

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

## Example 4: routine_rheumatology

*Routine rheumatology follow-up for rheumatoid arthritis on methotrexate.*

**Patient record:**

- **Upcoming appointment:** Rheumatoid arthritis follow-up, Sep 1 2026, 11:00 AM, with Dr. Laila Haddad (Rheumatology, Cascade Rheumatology)
- **Conditions:** Rheumatoid Arthritis (active, moderate)
- **Medications:** Methotrexate 15mg once weekly (prescribed by Dr. Laila Haddad, Rheumatology, Cascade Rheumatology, for Disease-modifying therapy)
- **Lab orders:** none on file
- **Vitals:** none on file
- **Past visits:** none on file

**AI-generated output:**

**Condition Management**

- Are there any adjustments to be made to my current treatment plan for Rheumatoid Arthritis?

**Medication Review**

- Is there a need to adjust the dosage or frequency of Methotrexate?

**Lifestyle & Prevention**

- Are there any lifestyle changes I can make to help manage my Rheumatoid Arthritis?

**Context summary shown to patient:** "The patient has Rheumatoid Arthritis and is taking Methotrexate as part of their treatment plan. They are due for a follow-up appointment with the Rheumatology department on 2026-09-01T11:00:00."

**Your ratings for this example:**

*Accuracy — rate EACH row below against the patient record above:*

- Condition Management: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Medication Review: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Lifestyle & Prevention: Fully Supported / Partially Supported / Unsupported / N/A — _______
- Context Summary: Fully Supported / Partially Supported / Unsupported / N/A — _______

- **Relevance** (are the questions relevant to this patient's actual conditions, medications, and appointment purpose?): Relevant / Partially Relevant / Not Relevant — _______
- **Clarity** (are the questions clearly phrased and understandable to a patient, not overly clinical or confusing?): Clear / Partially Clear / Confusing — _______
- **Usefulness** (would bringing these questions to the appointment genuinely help the conversation with the doctor?): Useful / Partially Useful / Not Useful — _______
- **Missing category?** (given the patient record above, is there a category you'd expect to see that's missing entirely from the output?): None missing / Condition Management / Medication Review / Lab Results & Monitoring / Lifestyle & Prevention / Follow-up Planning / Other (note below) — _______
- **Would you personally bring this to an appointment, if it were your own visit?** Yes / No / Not sure — _______
- **Notes** (anything confusing, redundant, or that stood out, positively or negatively?): _______

---

## Example 5: conflicting_cross_visit_notes

*Two past visits with the target doctor whose notes are in mild tension (one implies a recent dose change, the other says unchanged) — tests whether the model hedges rather than asserting either as settled fact.*

**Patient record:**

- **Upcoming appointment:** Thyroid follow-up, Sep 4 2026, 9:00 AM, with Dr. Elena Vance (Endocrinology, Bay Endocrinology)
- **Conditions:** Hashimoto's Thyroiditis (active)
- **Medications:** Levothyroxine 75mcg once daily, morning (prescribed by Dr. Elena Vance, Endocrinology, Bay Endocrinology, for Thyroid hormone replacement)
- **Lab orders:** none on file
- **Vitals:** none on file
- **Past visits:**
    - Jul 1 2026, 9:00 AM — Thyroid follow-up (with Dr. Elena Vance). Notes: "Dose unchanged at 75mcg; TSH stable."
    - May 1 2026, 9:00 AM — Thyroid follow-up (with Dr. Elena Vance). Notes: "Discussed possibly increasing dose pending next TSH; patient to follow up."

**AI-generated output:**

**Condition Management**

- Are there any changes in my Hashimoto's Thyroiditis symptoms since my last visit?

**Lab Results & Monitoring**

- What were my last TSH levels, and when were they ordered?
- Are there any pending lab tests or follow-up appointments related to my thyroid condition?

**Lifestyle & Prevention**

- Are there any lifestyle changes I can make to help manage my Hashimoto's Thyroiditis?
- Are there any specific dietary recommendations or restrictions for my condition?

**Follow-up Planning**

- Are there any referrals or specialist appointments that need to be scheduled?

**Context summary shown to patient:** "The patient has Hashimoto's Thyroiditis and is on Levothyroxine for thyroid hormone replacement. The purpose of the upcoming appointment is for a thyroid follow-up, and the patient's last TSH levels were stable. The patient's symptoms and medication regimen will be discussed during the appointment."

**Your ratings for this example:**

*Accuracy — rate EACH row below against the patient record above:*

- Condition Management: Fully Supported / Partially Supported / Unsupported / N/A — _______
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

## Example 6: medication_mentioned_only_in_past_notes

*A medication was discontinued and is only mentioned in a past visit's notes, not in the current medication list — the generated output should not treat it as an ongoing medication.*

**Patient record:**

- **Upcoming appointment:** Knee pain follow-up, Sep 3 2026, 1:00 PM, with Dr. Foster Reyes (Orthopedics, Granite Orthopedic Group)
- **Conditions:** Osteoarthritis, Right Knee (active)
- **Medications:** none on file
- **Lab orders:** none on file
- **Vitals:** none on file
- **Past visits:**
    - Jun 1 2026, 1:00 PM — Knee pain follow-up (with Dr. Foster Reyes). Notes: "Discontinued Ibuprofen due to GI upset; advised acetaminophen as needed instead, not currently prescribed."

**AI-generated output:**

**Condition Management**

- You have osteoarthritis in your right knee. What are the current treatment options, and are there any changes to your management plan since our last visit?

**Medication Review**

- You were advised to discontinue ibuprofen due to GI upset and switch to acetaminophen as needed. Are there any concerns about this change, and are there any alternative pain management options we should consider?

**Lab Results & Monitoring**

- Since our last visit, what are the current lab results for your osteoarthritis, and are there any pending tests or follow-ups that we should be aware of?

**Lifestyle & Prevention**

- As you have osteoarthritis, it's essential to maintain a healthy weight to reduce stress on your joints. What lifestyle changes can you make to support your weight management, and are there any specific exercises or activities that you should avoid?

**Follow-up Planning**

- Our next visit is scheduled for 2026-09-03T13:00:00. Are there any specific topics you'd like to discuss or any concerns you'd like to address before then?

**Context summary shown to patient:** "You have osteoarthritis in your right knee, and we previously discussed discontinuing ibuprofen due to GI upset. We should review your current treatment options and consider alternative pain management strategies."

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

## Example 7: inactive_condition_not_active_management

*Patient has one resolved condition and one active condition; the resolved one should not generate active-management questions.*

**Patient record:**

- **Upcoming appointment:** Diabetes follow-up, Sep 3 2026, 11:00 AM, with Dr. Elena Vance (Endocrinology, Bay Endocrinology)
- **Conditions:** Type 2 Diabetes Mellitus (active); Gestational Diabetes (resolved)
- **Medications:** Metformin 500mg twice daily (prescribed by Dr. Elena Vance, Endocrinology, Bay Endocrinology, for Blood sugar control)
- **Lab orders:** none on file
- **Vitals:** none on file
- **Past visits:** none on file

**AI-generated output:**

**Condition Management**

- What are the current blood sugar targets for my Type 2 Diabetes Mellitus, and are they being met?
- Are there any changes to my medication regimen or dosage that need to be discussed?

**Medication Review**

- Can I expect any changes to my Metformin dosage or schedule in the future?

**Lab Results & Monitoring**

- Are there any pending lab results or tests that need to be discussed?

**Lifestyle & Prevention**

- What lifestyle changes can I make to improve my blood sugar control and overall health?
- Are there any specific dietary or exercise recommendations for my Type 2 Diabetes Mellitus?

**Follow-up Planning**

- Is there a need for any follow-up appointments or tests in the near future?
- Are there any concerns or issues that need to be addressed before my next appointment?

**Context summary shown to patient:** "The patient has Type 2 Diabetes Mellitus and is currently taking Metformin. The purpose of the visit is to follow up on their diabetes management and discuss any necessary changes to their treatment plan."

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

## Example 8: vitals_only_no_labs

*A vitals trend present with no lab orders at all — isolates vitals-only grounding, distinct from groundedness_labs_vitals which has both.*

**Patient record:**

- **Upcoming appointment:** Weight management follow-up, Sep 5 2026, 1:00 PM, with Dr. Alex Kim (Family Medicine, Riverside Family Practice)
- **Conditions:** Overweight (active)
- **Medications:** none on file
- **Lab orders:** none on file
- **Vitals:** 195 lbs, BMI 28.9, 128/82, measured 2026-08-15; 201 lbs, BMI 29.8, 130/84, measured 2026-05-15
- **Past visits:** none on file

**AI-generated output:**

**Condition Management**

- What is the current plan for managing my overweight condition, and are there any changes to be made to my treatment plan?

**Lifestyle & Prevention**

- What lifestyle changes can I make to support my weight loss goals, and are there any specific dietary recommendations for my condition?

**Follow-up Planning**

- What is the expected weight loss goal for this follow-up appointment, and are there any specific metrics or measurements that will be tracked?

**Context summary shown to patient:** "The patient is a 41-year-old with an active overweight condition, and this follow-up appointment is scheduled to discuss weight management. The patient's vitals have shown a steady increase in weight and BMI over the past few months, with the most recent reading on 2026-08-15 showing a weight of 195 lbs and a BMI of 28.9. The patient's blood pressure has also been monitored, with the most recent reading on 2026-08-15 showing a BP of 128/82."

**Your ratings for this example:**

*Accuracy — rate EACH row below against the patient record above:*

- Condition Management: Fully Supported / Partially Supported / Unsupported / N/A — _______
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

## Example 9: max_density_multi_comorbidity

*Dense profile: 4 conditions, 5 medications, multiple labs, and a long past-visit history — stresses context-selection budget and the 15-question ceiling simultaneously.*

**Patient record:**

- **Upcoming appointment:** Comprehensive endocrine follow-up, Sep 5 2026, 9:00 AM, with Dr. Elena Vance (Endocrinology, Bay Endocrinology)
- **Conditions:** Type 2 Diabetes Mellitus (active); Hashimoto's Thyroiditis (active); Essential Hypertension (active); Hyperlipidemia (active)
- **Medications:** Metformin 1000mg twice daily (prescribed by Dr. Elena Vance, Endocrinology, Bay Endocrinology, for Blood sugar control); Levothyroxine 88mcg once daily, morning (prescribed by Dr. Elena Vance, Endocrinology, Bay Endocrinology, for Thyroid hormone replacement); Lisinopril 20mg once daily (prescribed by Dr. Elena Vance, Endocrinology, Bay Endocrinology, for Blood pressure control); Atorvastatin 40mg once daily at bedtime (prescribed by Dr. Elena Vance, Endocrinology, Bay Endocrinology, for Cholesterol management); Empagliflozin 10mg once daily (prescribed by Dr. Elena Vance, Endocrinology, Bay Endocrinology, for Glycemic and cardiorenal protection)
- **Lab orders:** HbA1c, ordered 2026-08-20; TSH, ordered 2026-08-20; Lipid Panel, ordered 2026-07-01
- **Vitals:** 210 lbs, BMI 31.4, 134/86, measured 2026-08-20
- **Past visits:**
    - May 15 2026, 9:00 AM — Diabetes follow-up (with Dr. Elena Vance). Notes: "A1C improved from 8.1 to 7.4."
    - Feb 15 2026, 9:00 AM — Diabetes follow-up (with Dr. Elena Vance). Notes: "Started Empagliflozin."

**AI-generated output:**

**Condition Management**

- How does my Hashimoto's Thyroiditis treatment plan align with my current medication regimen?
- What are the current blood pressure targets for my Essential Hypertension, and are they being met?
- What are the current lipid targets for my Hyperlipidemia, and are they being met?

**Medication Review**

- Are there any potential interactions between my medications, such as Metformin, Levothyroxine, Lisinopril, Atorvastatin, and Empagliflozin?
- Are there any dosage adjustments or changes to my medication regimen that need to be made?

**Lab Results & Monitoring**

- What are the results of my recent HbA1c test (ordered: 2026-08-20)?
- What are the results of my recent TSH test (ordered: 2026-08-20)?
- What are the results of my recent Lipid Panel test (ordered: 2026-07-01)?
- Are there any pending lab orders or tests that need to be scheduled?

**Lifestyle & Prevention**

- What lifestyle changes or recommendations can I make to better manage my Type 2 Diabetes Mellitus and Hashimoto's Thyroiditis?
- Are there any specific dietary changes or restrictions that I need to follow?

**Follow-up Planning**

- Are there any referrals or specialist appointments that need to be scheduled?

**Context summary shown to patient:** "The patient has multiple chronic conditions, including Type 2 Diabetes Mellitus, Hashimoto's Thyroiditis, Essential Hypertension, and Hyperlipidemia. They are currently taking several medications to manage these conditions. The patient has recent lab orders and vitals data, and we need to review their treatment plans and make any necessary adjustments."

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

## Example 10: groundedness_labs_vitals

*Endocrinology visit with lab orders and a vitals trend present, so the groundedness entity-match check has real entities to find.*

**Patient record:**

- **Upcoming appointment:** Thyroid check, Aug 2 2026, 10:00 AM, with Dr. Elena Vance (Endocrinology, Bay Endocrinology)
- **Conditions:** Hashimoto's Thyroiditis (active)
- **Medications:** Levothyroxine 75mcg once daily, morning (prescribed by Dr. Elena Vance, Endocrinology, Bay Endocrinology, for Thyroid hormone replacement)
- **Lab orders:** TSH, ordered 2026-07-15
- **Vitals:** 165 lbs, BMI 26.1, 122/78, measured 2026-07-15; 168 lbs, BMI 26.6, 124/80, measured 2026-04-10
- **Past visits:** none on file

**AI-generated output:**

**Medication Review**

- Are there any alternative medications or dosages that could be used for thyroid hormone replacement?

**Lab Results & Monitoring**

- What were the results of the TSH test ordered on 2026-07-15, and are they available?
- Are there any pending lab results or tests that need to be discussed during this appointment?

**Lifestyle & Prevention**

- What are some lifestyle changes that could help manage Hashimoto's Thyroiditis, and how can I implement them?

**Follow-up Planning**

- Is there a need for a follow-up appointment to check on the effectiveness of the current treatment plan?
- Are there any referrals or specialist appointments that need to be scheduled in the near future?

**Context summary shown to patient:** "The patient has Hashimoto's Thyroiditis and is taking Levothyroxine for thyroid hormone replacement. The upcoming appointment is for a thyroid check, and the patient's recent vitals show a weight of 165 lbs and a BMI of 26.1. The patient's current medication regimen and lab results will be discussed during the appointment."

**Your ratings for this example:**

*Accuracy — rate EACH row below against the patient record above:*

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