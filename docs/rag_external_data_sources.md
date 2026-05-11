# RAG External Data Sources

This file is documentation only. It should not be ingested into the Mercy General RAG knowledge base.

Mercy General is a fictional hospital, so hospital-specific policy should be created internally for the demo and kept consistent with the current doctor directory, Supabase schema, and scheduling rules.

## Create Internally For This Project

These are hospital-specific and should not be downloaded from another hospital:

- Parking instructions
- Clinic hours and holiday schedules
- Accepted insurance list
- Self-pay and billing policies
- Referral requirements
- Department booking rules
- Appointment preparation instructions
- Cancellation/no-show policy
- Call center scripts and escalation rules

Current project sources:

- `data/knowledge_base/mercy_general_operational_policy.md`
- `data/knowledge_base/department_services.md`
- `data/knowledge_base/symptom_department_routing_guide.md`
- `data/knowledge_base/faq_and_call_scripts.md`
- `docs/doctors.md`

## Use Structured Systems Instead Of RAG

These should come from Supabase/EHR tools, not downloaded documents:

- Provider directory records
- Live appointment slots
- Doctor availability
- Patient identity
- Patient clinical profile
- Insurance eligibility checks
- Referral status
- Booking, cancellation, and reschedule confirmation

## Public Sources To Download Later

Use these only if the project later needs general patient-education content. They should be filtered and clearly separated from Mercy General policy.

### MedlinePlus

MedlinePlus is the best public source for patient-friendly health topic summaries.

- Website: <https://medlineplus.gov/>
- Developer info: <https://medlineplus.gov/fordevelopers.html>
- Health topic XML: <https://medlineplus.gov/xml.html>
- Web service: <https://medlineplus.gov/about/developers/webservices/>

### CDC

CDC is useful for public health, vaccines, infection prevention, flu/COVID, and travel health guidance.

- Website: <https://www.cdc.gov/>
- Data portal: <https://data.cdc.gov/>
- Vaccines: <https://www.cdc.gov/vaccines/>

### NIH / NLM Institutes

NIH sources can support condition education if carefully filtered.

- National Library of Medicine: <https://www.nlm.nih.gov/>
- National Heart, Lung, and Blood Institute: <https://www.nhlbi.nih.gov/>
- National Institute of Diabetes and Digestive and Kidney Diseases: <https://www.niddk.nih.gov/>
- National Cancer Institute: <https://www.cancer.gov/>
- National Institute of Neurological Disorders and Stroke: <https://www.ninds.nih.gov/>

### MedQuAD

MedQuAD can be used for a larger medical QA retrieval experiment, but it should not replace Mercy General policy.

- Original GitHub: <https://github.com/abachaa/MedQuAD>
- Hugging Face: <https://huggingface.co/datasets/prithvi1029/medquad-medical-qa>
- Retrieval-ready variant: <https://huggingface.co/datasets/cristian-untaru/medquad-retrieval-pretriage>

## Avoid As Primary KB

HealthCareMagic, MedDialog, and PubMedQA are not good primary sources for this voice receptionist. HealthCareMagic and MedDialog may include direct diagnosis or medication advice. PubMedQA is biomedical research QA, not patient-facing hospital operations content.
