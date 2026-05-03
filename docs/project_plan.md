# AI Voice Agent: Project Plan

## Phase 1: Data Downloading
- [x] Download generated FHIR patient medical records.
- [x] Obtain the list of the 25 validated doctors for the hospital (Mercy General).
- [x] Download healthcare QA knowledge base (`healthcare_qa.csv`).

## Phase 2: Data Cleaning (Complete)
- [x] **Extract Doctors:** Extract the 25 authorized Mercy General doctors into individual JSON files.
  - *Why:* To establish a strict, validated list of staff for the AI agent to reference.
- [x] **Process Patients:** Filter patient records and remap their medical history to our 25 specific doctors.
  - *Why:* To ensure all patient encounters map to our valid doctors, maintaining data consistency.
- [ ] **Clean `healthcare_qa.csv` Knowledge Base (Pending):**
  - *What:* Filter the general healthcare Q&A dataset to remove topics or treatments that fall outside the specialties of our 25 doctors.
  - *Why:* To prevent the AI Voice Agent from answering questions or promising treatments for conditions our hospital cannot handle.
- [x] **Filter FHIR "Junk" Data for LLM (Complete):**
  - *What:* Create logic to strip out non-clinical resources (like `Claim` and `ExplanationOfBenefit` billing data) from the patient JSON files before sending them to the LLM. (Logic documented in patient_profile_template.md & system_design_decisions.md)
  - *Why:* To prevent the LLM from getting confused by massive amounts of irrelevant billing data, which saves tokens and improves the agent's response speed and accuracy.

## Phase 3: Feature Definition (In Progress)
- Brainstorm and list the core features that should be included in the system.
- Define what the AI Voice Agent needs to be able to do.
- Outline the functions required for the `ehr_server.py` API.

## Phase 4: API & Integration Development
- Build the `ehr_server.py` API.
- Connect the medical RAG pipeline for triage.
- Integrate the AI Voice Agent with the backend data.
