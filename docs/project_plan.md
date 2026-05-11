# AI Voice Agent: Project Plan

## Phase 1: Data Downloading
- [x] Download generated FHIR patient medical records.
- [x] Obtain the list of the 25 validated doctors for the hospital (Mercy General).
- [x] Create curated Mercy General RAG knowledge base (`data/knowledge_base/`).

## Phase 2: Data Cleaning (Complete)
- [x] **Extract Doctors:** Extract the 25 authorized Mercy General doctors into individual JSON files.
  - *Why:* To establish a strict, validated list of staff for the AI agent to reference.
- [x] **Process Patients:** Filter patient records and remap their medical history to our 25 specific doctors.
  - *Why:* To ensure all patient encounters map to our valid doctors, maintaining data consistency.
- [x] **Create Mercy General Policy Knowledge Base:**
  - *What:* Split hospital-specific FAQ, department services, referral rules, appointment prep, and symptom-to-department routing into RAG-ready files.
  - *Why:* To ground the agent in approved hospital policy without relying on general medical QA data.
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

## Phase 5: System Architecture Design ✅ COMPLETE
- [x] **Define the full system architecture** — WebRTC + Deepgram + LangGraph + FastAPI + Supabase + pgvector. See `docs/system_architecture.md`.
- [x] **Design `ehr_server.py` API contract** — 9 endpoints defined with full request/response schemas. See `docs/component_architectures.md`.
- [x] **Design the RAG pipeline architecture** — Supabase Vector / `pgvector` + fixed-model embeddings, cosine similarity, top-3 retrieval.
- [x] **Design the Voice Agent tool-calling schema** — 7 tools mapped to specific LangGraph nodes with restricted access per node.
- [x] **Design call state machine** — 8 nodes (AUTH → ROUTING → SCHEDULING → CONFIRM + NEW_PATIENT, FAQ, CROSS_COVERAGE, EMERGENCY) with conditional edges.
- [x] **Create architecture diagrams** — High-level system diagram, sequence diagram, state machine diagram, per-component internal architecture.
- [x] **Document all design decisions** — WebRTC over Vapi, LangGraph state machine over ReAct, Deepgram Nova-2 for STT, latency budget < 2s.

## Phase 6: API & Integration Development (Next)
- [ ] Build WebRTC frontend (`frontend/index.html`, `app.js`) — browser call interface.
- [ ] Build `voice_server.py` — WebSocket handler bridging browser ↔ Deepgram ↔ LangGraph.
- [ ] Build `ehr_server.py` FastAPI backend — all 9 REST endpoints connecting to Supabase.
- [ ] Build `rag_pipeline.py` — ingest the approved RAG data files from `data/knowledge_base/` into Supabase Vector / `pgvector`.
- [ ] Build `agent_graph.py` — LangGraph state machine with all 8 nodes.
- [ ] Build tools (`src/tools/`) and prompts (`src/prompts/`) for each node.
- [ ] Integrate all components end-to-end.
- [ ] End-to-end testing via WebRTC browser calls.
