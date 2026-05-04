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

## Phase 3: Feature Definition (Complete)
- [x] Brainstorm and list the core features that should be included in the system.
- [x] Define what the AI Voice Agent needs to be able to do.
- [x] Outline the functions required for the `ehr_server.py` API.

## Phase 4: Database Setup & Migration (Supabase) ✅ COMPLETE
- [x] Set up Supabase project and get connection keys.
- [x] Design PostgreSQL hybrid schema (Doctors, Patients, Medical Profiles, Appointments).
  - *Doctors table:* FHIR identity fields + Mercy General hospital metadata (focus, room, extension, booking_status, experience) + `raw_fhir_data` JSONB.
  - *Medical Profiles table:* Rich `clinical_data` JSONB following `patient_profile_template.md` (vitals, labs, conditions, meds, procedures, immunizations, care plans, visits, allergies, insurance).
- [x] Write and test the migration script (`migrate_to_supabase.py`) locally before uploading.
  - *Fixed:* Procedures capped at 10 most recent (was 115+).
  - *Fixed:* Immunizations de-duplicated by vaccine name, keeping most recent date only.
- [x] **Run migration script** — All 25 doctors and 1,000+ patients successfully seeded into Supabase. ✅

## Phase 5: System Architecture Design (Current)
- [ ] **Define the full system architecture** — Map every component (Vapi, Deepgram, FastAPI, Supabase, ChromaDB) and how data flows between them during a live call.
- [ ] **Design `ehr_server.py` API contract** — Define all endpoints, request/response schemas, and authentication strategy.
- [ ] **Design the RAG pipeline architecture** — Define ChromaDB ingestion flow, embedding model choice, and retrieval strategy for `healthcare_qa.csv`.
- [ ] **Design the Voice Agent tool-calling schema** — Define the exact function signatures and payloads the LLM will use to call the EHR API and RAG pipeline during a call.
- [ ] **Design call state machine** — Map the full conversational state flow (Emergency Screen → Auth → Routing → Scheduling → Confirmation).
- [ ] **Create architecture diagrams** — Produce component diagram, sequence diagram for a full call, and data flow diagram.
- [ ] **Document all design decisions** — Record choices around LLM provider, embedding model, API auth, and latency targets.

## Phase 6: API & Integration Development (Pending)
- Build `ehr_server.py` FastAPI backend (connecting to Supabase).
- Build `rag_pipeline.py` — ingest `healthcare_qa.csv` into ChromaDB.
- Build and configure the Voice Agent (Vapi + LLM + tools).
- Integrate all components end-to-end.
- End-to-end testing via WebRTC and phone calls.
