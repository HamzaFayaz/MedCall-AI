# Progress

Track your progress through the Mercy General Voice Agent. Update this file as you complete phases and components — Claude Code reads this to understand where you are in the project.

## Convention

- `[ ]` = Not started
- `[-]` = In progress
- `[x]` = Completed

## Phases

### Phase 1: Data Downloading — **complete**

- [x] Synthea FHIR patient bundles — `scripts/download_synthea_data.py`
- [x] Legacy HuggingFace healthcare QA dataset — `scripts/download_qa_data.py`, `data/healthcare_qa.csv`
- [x] Curated Mercy General RAG knowledge base — `data/knowledge_base/` (four approved markdown files per `PRD.md` §9)

### Phase 2: Data Cleaning — **complete**

- [x] Extract 25 Mercy General doctors — `scripts/extract_25_doctors.py` → `data/processed/doctors/`
- [x] Process and remap patients to valid doctors — `scripts/process_patients.py` → `data/processed/patients/`
- [x] Filter FHIR billing junk from LLM context — `Claim` / `ExplanationOfBenefit` excluded per `docs/patient_profile_template.md`
- [x] Hospital policy KB split into RAG-ready files — `data/knowledge_base/` aligned with `docs/doctors.md` departments

### Phase 3: Feature Definition — **complete**

- [x] Six core agent features defined — `PRD.md` §5, `docs/features.md`
- [x] Conversational call flow / state machine outlined — `PRD.md` §6
- [x] EHR API surface outlined — `PRD.md` §7–8, `system design/04-component-backend-ehr.md`
- [x] Scheduling and cross-coverage rules documented — `docs/scheduling_logic.md`

### Phase 4: Database Setup & Migration — **complete**

- [x] Supabase DDL for EHR tables — `scripts/supabase_setup.sql` (`doctors`, `patients`, `medical_profiles`, `appointments`)
- [x] Hybrid schema + `clinical_data` JSONB documented — `docs/supabase_schema.md`
- [x] Migration script — `scripts/migrate_to_supabase.py` (25 doctors + 1,000+ patients seeded per `PRD.md` §8, §10)

**Not in Phase 4:** RAG `knowledge_chunks` / `pgvector` (Component 05), voice gateway, orchestrator graph, `ehr_server` REST API

### Phase 5: System Architecture Design — **complete**

- [x] End-to-end architecture — `system design/01-main-system-design.md`
- [x] Voice & realtime component — `system design/02-component-voice-realtime.md`
- [x] Orchestration component — `system design/03-component-orchestration.md`
- [x] Backend EHR component — `system design/04-component-backend-ehr.md`
- [x] Data + RAG component — `system design/05-component-data-rag.md`
- [x] Trust, security, operations — `system design/06-trust-security-operations.md`

**Implementation plans completed:** `.agent/Plans/02_voice_layer_cards.md`, `.agent/Plans/05_data_rag_cards.md`

**Implementation plans in progress:** `.agent/Plans/03_orchestrator_cards.md` (index) · `.agent/Plans/03_orchestrator_01_session_start_emergency_gate.md` (sub-plan 01: `session_start`, `EMERGENCY_GATE`)

**Implementation plans not started:** Components 01 (main deploy), 03 orchestrator sub-plans 02–06, 04 (EHR API cards), 06 (trust/ops)

### Phase 6: API & Integration Development — **in progress**

- [x] FastAPI app shell + health — `main.py`
- [x] WebRTC client — `client/index.html`, `client/app.js`
- [-] Voice path wired to minimal LLM chat — `src/gateway/` → `src/orchestrator/` (single `chat` node; no tools, no RAG, no EHR)
- [ ] `ehr_server` / EHR REST endpoints — `src/ehr/routes/` stub only; design in `system design/04-component-backend-ehr.md`
- [ ] Full LangGraph state machine — emergency gate, auth, scheduling, tool allowlists per `system design/03-component-orchestration.md`
- [ ] End-to-end voice call: STT → orchestrator tools → EHR + RAG → TTS with citations and booking

---

## Component 02: Voice & Realtime Layer — **complete & validated**

Plan: [.agent/Plans/02_voice_layer_cards.md](.agent/Plans/02_voice_layer_cards.md) · Design: [system design/02-component-voice-realtime.md](system%20design/02-component-voice-realtime.md)

- [x] Card 1: WebRTC signaling API — `src/gateway/server.py` (`POST /webrtc/offer`, ICE/STUN, rate limit)
- [x] Card 2: Deepgram STT adapter — `src/adapters/stt_deepgram.py`
- [x] Card 3: Deepgram TTS adapter (+ pyttsx3 fallback) — `src/adapters/tts_deepgram.py`, `src/adapters/tts_factory.py`
- [x] Card 4: Basic WebRTC client — `client/`
- [x] Card 5: Bidirectional audio track — `src/gateway/audio_track.py`
- [x] Card 6: VAD & barge-in — `src/gateway/vad.py`, `src/gateway/barge_in.py`, `speak.cancel` / STT final suppression
- [x] Card 7: Session manager — `src/gateway/session.py` (lifecycle, events channel, orchestrator hook)

**Known gaps (non-blocker for cards):** production TURN, full graceful-degradation matrix — see `Issues/03_voice_layer_fixes.md`

---

## Component 05: Data + RAG Layer — **in progress**

Plan: [.agent/Plans/05_data_rag_cards.md](.agent/Plans/05_data_rag_cards.md) · Design: [system design/05-component-data-rag.md](system%20design/05-component-data-rag.md)

### Cards 1–5 — **complete**

- [x] Card 1: Supabase vector schema — `scripts/supabase_rag_vector_db.sql` (`knowledge_chunks`, similarity RPC)
- [x] Card 2: KB loader and chunker — `src/rag/ingest.py` (four approved markdown files only)
- [x] Card 3: Embedding adapter — `src/rag/embeddings.py` (`Qwen/Qwen3-Embedding-0.6B`, 1024-dim)
- [x] Card 4: Supabase RAG vector DB — `src/rag/vector_db.py`
- [x] Card 5: RAG service API — `src/rag/service.py` (`retrieve_knowledge`, `OUT_OF_SCOPE_PATTERNS`, emergency keyword gate)

### Cards 6–8 — **not started / on hold**

- [ ] Card 6: Orchestrator tool contract — `retrieve_policy_knowledge`; blocked on full orchestrator (`system design/03-component-orchestration.md`)
- [ ] Card 7: Retrieval evaluation — golden set + `Rag Evaluation/evaluate_rag_retrieval.py` exist; production guardrails need orchestrator
- [ ] Card 8: Answer safety evaluation — blocked on orchestrator + LLM answer path

**Validation** *(last run: `Rag Evaluation/last_retrieval_report.txt` — 2026-05-13)*

- [x] 11 / 12 golden retrieval cases PASS (parking, Medicaid, orthopedics prep, belly/neck pain routing, cardiology referral, emergency keywords, dermatology routing, out-of-scope availability, empty query)
- [ ] `out_of_scope_patient_clinical` — "What are my current medications?" returned `ok` instead of `out_of_scope` (orchestrator routing + stronger RAG patterns)

**Not in Component 05:** doctor availability, appointment slots, patient identity, booking side effects (structured EHR tools only)

---

## Component 03: Orchestration — **in progress (stub only)**

Design: [system design/03-component-orchestration.md](system%20design/03-component-orchestration.md)

- [x] Minimal LangGraph chat wired to WebRTC STT finals — `src/orchestrator/graph.py`, `src/orchestrator/__init__.py`
- [ ] Emergency gate on every utterance before graph advancement
- [ ] Full call state machine (identification → routing → scheduling → insurance)
- [ ] Tool allowlists per node (EHR + RAG tools)
- [ ] RAG tool invocation from graph (depends on Component 05 Card 6)

---

## Component 04: Backend EHR API — **not started**

Design: [system design/04-component-backend-ehr.md](system%20design/04-component-backend-ehr.md)

- [ ] FastAPI `ehr_server` with provider / patient / appointment endpoints
- [ ] Supabase-backed reads and idempotent writes
- [ ] Token-efficient `GET /patients/{id}/profile` for LLM context
