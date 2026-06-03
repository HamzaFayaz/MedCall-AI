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

**Implementation plans completed:** `.agent/Plans/03_orchestrator_01_session_start_emergency_gate.md` (sub-plan 01 — v1 behavior: session + keyword gate)

**Implementation plans in progress:** `.agent/Plans/03_orchestrator_cards.md` (index) · [03_orchestrator_02_langgraph_patient_identify.md](.agent/Plans/03_orchestrator_02_langgraph_patient_identify.md) (LangGraph step 0 + `PATIENT_IDENTIFY`)

**Implementation plans not started:** Components 01 (main deploy), 03 orchestrator sub-plans 03–06, 04 (EHR API cards), 06 (trust/ops)

### Phase 6: API & Integration Development — **in progress**

- [x] FastAPI app shell + health — `main.py`
- [x] WebRTC client — `client/index.html`, `client/app.js`
- [x] Voice path wired to orchestrator — `handle_transcript` thin adapter → LangGraph (`session_start`, `EMERGENCY_GATE`, `PATIENT_IDENTIFY`)
- [ ] `ehr_server` / EHR REST endpoints — `src/ehr/routes/` stub only; design in `system design/04-component-backend-ehr.md`
- [ ] Full call state machine (auth, scheduling, tools) — sub-plan 02+ (after LangGraph refactor)
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

## Component 03: Orchestration — **in progress**

Design: [system design/03-component-orchestration.md](system%20design/03-component-orchestration.md)

Plan (sub-plan 01): [.agent/Plans/03_orchestrator_01_session_start_emergency_gate.md](.agent/Plans/03_orchestrator_01_session_start_emergency_gate.md)

### Sub-plan 01 — **complete** (v1: behavior outside LangGraph)

- [x] Minimal LangGraph `chat` stub — `src/orchestrator/graph.py`
- [x] Session fields + in-memory store — `state.py`, `session_lifecycle.py`; `start_session` from `server.py`
- [x] Keyword emergency gate before LLM — `emergency_gate.py`, `emergency_phrases.py`; wired in `handle_transcript`
- [x] Tests + `scripts/chat_terminal.py`

*Note: `session_start` / `EMERGENCY_GATE` as **LangGraph nodes** + unified graph memory are **not** sub-plan 01 scope — they are **step 0 of sub-plan 02** (before `PATIENT_IDENTIFY`).*

### Sub-plan 02 — **in progress** (prerequisite + first conversational nodes)

**Step 0 — LangGraph refactor (do this before new nodes):**

- [x] Single graph `CallState`: `messages`, `session_ended`, `emergency_*`, `active_node`, `patient_id`, … — `src/orchestrator/call_state.py`
- [x] Move `session_start` + `EMERGENCY_GATE` into `StateGraph` (code-only nodes + conditional edges) — `src/orchestrator/graph.py`, `nodes/`
- [x] Orchestration inside graph: session, emergency, routing, LLM — not in `__init__.py`
- [x] **Thin `handle_transcript` adapter** (keep, shrink — do not delete):
  - [x] Parse `event` (`session_id`, `text`); cheap guards (`if not text: return ""`)
  - [x] `await graph.ainvoke(..., config={"configurable": {"thread_id": session_id}})`
  - [x] Map final state → spoken `str` for gateway/TTS (`last_reply`)
  - [x] Gateway + `chat_terminal.py` keep calling `handle_transcript` only (no LangGraph imports in `session.py`)
- [x] One memory source of truth: graph state + `MemorySaver` checkpointer; `_sessions` synced after `ainvoke`
- [x] Update tests for graph path — `tests/test_graph_emergency.py`, updated lifecycle/handle_transcript tests

**Why thin adapter (not call graph from gateway directly):** stable voice↔orchestrator contract; separate gateway `CallSession` (media) from graph `thread_id` (conversation); one place to fix invoke/config; easier mocking; terminal and WebRTC stay identical.

**Then — node implementation:**

- [x] `PATIENT_IDENTIFY` — `nodes/patient_identify.py`, `tools/lookup_patient.py`, `prompts.py`; `VERIFY_RETURNING` / `REGISTER_SHELL_PROFILE` stubs
- [ ] Tool allowlists per node (EHR tools as EHR API lands)

### Later sub-plans (03+)

- [ ] `CLINICAL_ROUTE`, `RAG_ANSWER`, `SCHEDULING`, …
- [ ] RAG tool invocation from graph (depends on Component 05 Card 6)
- [ ] Emergency v2: tune keywords + optional LLM for ambiguous utterances

---

## Component 04: Backend EHR API — **not started**

Design: [system design/04-component-backend-ehr.md](system%20design/04-component-backend-ehr.md)

- [ ] FastAPI `ehr_server` with provider / patient / appointment endpoints
- [ ] Supabase-backed reads and idempotent writes
- [ ] Token-efficient `GET /patients/{id}/profile` for LLM context
