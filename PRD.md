# PRD — Healthcare Patient Scheduler & Intake Voice Agent
**Version:** 1.0 | **Last Updated:** May 4, 2026 | **Status:** Phase 5 (Architecture Design)

> **AI Onboarding Note:** This is the single source-of-truth document for this project. Reading this file alone gives you full context to understand the system, its current state, and what needs to be built next. Reference the other `.md` files under `docs/` for deeper detail on specific topics.

---

## 1. Product Overview

**What it is:** An AI-powered voice receptionist for **Mercy General Hospital** (Seattle, WA). Patients connect over **WebRTC** (browser or app) and speak naturally to the agent to handle all routine front-desk tasks without speaking to a human.

**Why it exists:** Hospital front desks spend 60–70% of their time on routine, repeatable tasks (booking, rescheduling, answering FAQs). This agent automates those tasks entirely, freeing staff for complex patient care.

**What it does:**
- Books, reschedules, and cancels appointments via voice
- Authenticates returning patients (Name + DOB + Phone)
- Onboards new patients (creates a "shell profile")
- Performs basic medical triage via an AI knowledge base
- Detects medical emergencies and immediately redirects to 911
- Collects insurance information for billing context

---

## 2. The Hospital: Mercy General

| Detail | Value |
|---|---|
| **Full Name** | Mercy General Hospital & Outpatient Center |
| **Main Address** | 4500 Mercy Boulevard, Seattle, WA 98104 |
| **North Clinic** | 1200 Northgate Way, Seattle, WA 98125 |
| **Hours (Outpatient)** | Mon–Fri 7AM–7PM, Sat 8AM–2PM (Urgent Care), Sun Closed |
| **ER** | Open 24/7 — (555) 800-9111 |
| **Main Line** | (555) 800-0000 |

### Accepted Insurance
**In-Network:** Blue Cross Blue Shield, Aetna, Cigna, UnitedHealthcare, Medicare (Parts A & B + Humana Advantage), Washington Apple Health (Medicaid — Primary Care & Pediatrics only; Specialists need pre-auth).
**Self-Pay:** 20% discount if paid at time of service. New patient consult: $250–$400.

---

## 3. Doctor Roster (25 Physicians, 8 Departments)

All doctor data is stored as individual JSON files in `data/processed/doctors/` and seeded into the Supabase `doctors` table.

| # | Department | Count | Booking Notes |
|---|---|---|---|
| 1 | Primary Care (Family & Internal Medicine) | 6 | Mix: accepting / waitlist |
| 2 | Emergency Medicine | 4 | Walk-ins ONLY — no scheduling |
| 3 | Pediatrics | 3 | Ages 0–18; vaccination records required |
| 4 | Women's Health (OB/GYN) | 3 | Some require referral |
| 5 | Cardiology | 2 | PCP referral required (unless PPO) |
| 6 | Orthopedics & Sports Medicine | 2 | Must bring recent X-rays/MRIs |
| 7 | General Surgery | 2 | Referral only |
| 8 | Specialty (GI, Neurology, Psychiatry) | 3 | Mix: accepting / referral required |

> See `docs/doctors.md` for the full individual doctor roster with names, focus areas, room numbers, and extensions.

---

## 4. Technology Stack

### Core Services

| Component | Technology | Purpose |
|---|---|---|
| **Real-time voice (primary)** | WebRTC | Peer connection and media path for bidirectional audio between patient client and backend/signaling; core transport for the voice agent |
| **Speech-to-Text** | Deepgram | Real-time, low-latency transcription of patient speech |
| **LLM** | TBD (GPT-4o / Claude 3.5) | Core reasoning, intent recognition, response generation |
| **TTS** | TBD (e.g. ElevenLabs) | Converts LLM text output back to voice |

### Backend & Data

| Component | Technology | Purpose |
|---|---|---|
| **Mock EHR API** | FastAPI (`ehr_server.py`) | Simulates an Epic EHR; exposes patient/doctor/appointment endpoints |
| **RAG Knowledge Base** | ChromaDB + `healthcare_qa.csv` | Semantic search for medical triage Q&A |
| **Database** | Supabase (PostgreSQL + JSONB) | Cloud-hosted, production-grade data store |
| **Data Standard** | FHIR R4 JSON | Industry-standard medical record format |
| **Data Generator** | Synthea | Source of realistic, HIPAA-safe fake patient & provider records |
| **QA Dataset** | `adrianf12/healthcare-qa-dataset` (HuggingFace) | Medical Q&A for RAG pipeline |

---

## 5. The 6 Core Agent Features

### Feature 1: Smart Appointment Scheduling
- Book, reschedule, or cancel appointments via natural conversation
- **Cross-Coverage Logic:** If a patient's doctor is unavailable, offer the next available doctor in the same department
- **ER Routing:** Detect ER-type calls and direct to walk-in (no booking slot needed)

### Feature 2: Patient Authentication & Profile Fetching
- Verify identity: Name + Date of Birth + Phone number
- On match: pull the patient's full clinical summary from the EHR API (`GET /patients/{id}/profile`)
- The LLM receives the `clinical_data` JSONB as context for the conversation

### Feature 3: New Patient Onboarding
- If patient is not found in Supabase, transition to registration flow
- Collect minimum required info: Full Legal Name, DOB, Phone, Gender, Insurance
- Call `POST /patients` on the EHR API to instantly create a shell profile and Patient ID
- Book the appointment immediately after registration

### Feature 4: Conversational Medical Triage (RAG)
- Listen for symptom descriptions and route them through the ChromaDB RAG pipeline
- Return semantically matched answers from the medical QA dataset
- Hard restrictions: agent cannot diagnose, prescribe, or promise treatments outside the hospital's specialties

### Feature 5: Emergency Guardrails (Zero Tolerance)
- **Trigger Keywords:** chest pain, difficulty breathing, shortness of breath, sudden weakness, drooping face, severe bleeding, suicidal thoughts
- **Action:** Immediately interrupt all other flows
- **Script:** *"I am an automated assistant and it sounds like you are experiencing a medical emergency. Please hang up and dial 911 immediately."* → Terminate call

### Feature 6: Insurance & Basic Intake
- Collect primary health insurance provider name
- Collect chief complaint and duration of symptoms for doctor pre-briefing
- Pass collected data to the appointment record in Supabase

---

## 6. Call Flow (Conversational State Machine)

```
[WEBRTC SESSION START — patient audio connected]
      │
      ▼
┌─────────────────────────────────────────────────────────┐
│  STATE 0: Emergency Screening (Runs on every utterance) │
│  Detect: chest pain / bleeding / suicidal thoughts      │
│  → Terminate call immediately + 911 instruction         │
└─────────────────────────────────────────────────────────┘
      │ (no emergency detected)
      ▼
┌──────────────────────────────────┐
│  STATE 1: Patient Identification │
│  • Calling for self or other?    │
│  • Existing or new patient?      │
│  • Name + DOB                    │
└──────────────────────────────────┘
      │
      ├── [Returning Patient] → EHR lookup → load clinical profile
      │
      └── [New Patient] → Shell profile creation flow → POST /patients
      │
      ▼
┌──────────────────────────────────┐
│  STATE 2: Clinical Routing       │
│  • Reason for visit?             │
│  • Chronic vs. acute?            │
│  • Referral on file?             │
└──────────────────────────────────┘
      │
      ▼
┌──────────────────────────────────┐
│  STATE 3: Scheduling             │
│  • GET /providers?specialty=...  │
│  • Cross-coverage if needed      │
│  • Propose available slots       │
│  • POST /appointments to confirm │
└──────────────────────────────────┘
      │
      ▼
┌──────────────────────────────────┐
│  STATE 4: Insurance & Logistics  │
│  • Insurance provider?           │
│  • Remind: ID, card, meds        │
│  • MyChart pre-reg text sent     │
└──────────────────────────────────┘
      │
      ▼
[END CALL — Confirmation summary]
```

---

## 7. Scheduling & Cross-Coverage Rules

| Department | Cross-Coverage Policy |
|---|---|
| **Primary Care** | If requested PCP unavailable → offer any available Family/Internal Med doctor |
| **Emergency** | No booking — direct to ER walk-in; attending physician on shift will see them |
| **Specialists** | Stick to same doctor for continuity; cross-coverage only for urgent cases within same specialty |

**Required EHR API endpoints for scheduling:**
- `GET /providers?name={name}` — find specific doctor
- `GET /providers?specialty={specialty}` — find department doctors
- `GET /providers/availability?specialty={specialty}` — earliest open slot for any doctor in dept

---

## 8. Database Schema (Supabase — 4 Tables)

> **Status: Fully seeded ✅** — 25 doctors + 1,000+ patients live in Supabase.
> See `docs/supabase_schema.md` for the full column-level schema.
> See `scripts/supabase_setup.sql` for the DDL.
> See `scripts/migrate_to_supabase.py` for the migration logic.

### Table 1: `doctors`
Structured columns (id, npi, name, specialty, booking_status, room, extension, experience_years) + `raw_fhir_data JSONB` (full original FHIR Practitioner resource).

### Table 2: `patients`
Structured columns for authentication and lookup: id, mrn, first_name, last_name, dob, gender, phone, address.

### Table 3: `medical_profiles`
One-to-one link to `patients`. Contains `clinical_data JSONB` — a rich, token-efficient clinical summary used as LLM context.

### Table 4: `appointments`
Links `patients` and `doctors`. Columns: appointment_time, status (scheduled/completed/canceled), reason.

### `clinical_data` JSONB Structure (in `medical_profiles`)
Extracted and filtered from raw FHIR bundles. Contains:
`patient_info`, `recent_vitals`, `recent_lab_results`, `active_conditions`, `current_medications`, `procedures` (capped at 10), `immunizations` (de-duped), `ongoing_care_plans`, `recent_visits` (top 5), `allergies`, `insurance`

> **Filtered out:** `Claim` and `ExplanationOfBenefit` resources (billing junk that wastes LLM tokens).
> See `docs/patient_profile_template.md` for the full JSON schema + FHIR field mappings.

---

## 9. Project File Map

```
Voice Agent/
│
├── PRD.md                              ← YOU ARE HERE (single source of truth)
│
├── system design/                      ← Production architecture (Mermaid diagrams + components)
│
├── docs/
│   ├── project_plan.md                 ← Phase-by-phase progress tracker
│   ├── features.md                     ← 6 core features in detail
│   ├── doctors.md                      ← Full 25-doctor roster
│   ├── scheduling_logic.md             ← Cross-coverage rules
│   ├── supabase_schema.md              ← Full DB schema (4 tables)
│   ├── patient_profile_template.md     ← clinical_data JSONB schema + FHIR mapping
│   └── system_design_decisions.md      ← Why Supabase was chosen
│
├── data/
│   ├── fhir/                           ← Raw Synthea FHIR R4 JSON bundles (source)
│   ├── processed/
│   │   ├── doctors/                    ← 25 individual doctor JSON files
│   │   └── patients/                   ← 1,000+ processed patient JSON files
│   └── healthcare_qa.csv               ← Medical Q&A dataset (for RAG)
│
├── scripts/
│   ├── migrate_to_supabase.py          ← MAIN: migrates all data to Supabase ✅ DONE
│   ├── supabase_setup.sql              ← DDL for all 4 Supabase tables
│   ├── extract_25_doctors.py           ← Extracts doctors from raw FHIR
│   ├── process_patients.py             ← Cleans & remaps patients to our doctors
│   ├── download_qa_data.py             ← Downloads HuggingFace QA dataset
│   ├── download_synthea_data.py        ← Downloads Synthea FHIR bundles
│   ├── count_fhir_resources.py         ← Utility: count resource types
│   └── test_extraction.py             ← Tests data extraction logic
│
├── clinic_knowledge_base.md            ← Agent KB: hours, staff, triage protocol, FAQs
├── data_architecture_plan.md           ← Seed data plan (historical reference)
├── healthcare_agent_scope.md           ← Scope & requirements (historical reference)
├── project_stack.md                    ← Stack choices & fallback rationale
├── implementation_plan.md.resolved     ← Approved Phase 1-2 plan (historical reference)
├── requirements.txt                    ← Python dependencies
└── .env                                ← Supabase URL + anon key (not in git)
```

---

## 10. Project Progress

| Phase | Status | Summary |
|---|---|---|
| **Phase 1** — Data Downloading | ✅ Complete | Synthea FHIR + HuggingFace QA dataset acquired |
| **Phase 2** — Data Cleaning | ✅ Complete | 25 doctors extracted; patients processed & remapped; FHIR junk filtered |
| **Phase 3** — Feature Definition | ✅ Complete | 6 features defined; EHR API functions outlined |
| **Phase 4** — Database Setup & Migration | ✅ Complete | Supabase schema live; 25 doctors + 1,000+ patients seeded |
| **Phase 5** — System Architecture Design | 🔄 **CURRENT** | Design all components, API contracts, and diagrams |
| **Phase 6** — API & Integration Development | ⬜ Pending | Build `ehr_server.py`, RAG pipeline, Voice Agent |

---

## 11. What Needs to Be Done Next (Phase 5)

The data layer is complete and live. The next step is to **design the full system architecture** before writing a single line of application code. This includes:

1. **Full System Component Diagram** — All services (WebRTC signaling/media path, Deepgram, FastAPI, Supabase, ChromaDB) and their connections
2. **`ehr_server.py` API Contract** — Every endpoint, HTTP method, request params, response schema, and auth strategy
3. **RAG Pipeline Architecture** — Embedding model selection, ChromaDB collection design, retrieval strategy
4. **Voice Agent Tool-Calling Schema** — The exact JSON function definitions the LLM will use to call the EHR API and RAG system mid-call
5. **Call State Machine Diagram** — Formal state/transition diagram for the full call flow
6. **Sequence Diagram** — Full call lifecycle from ring to hangup, showing every service interaction
7. **Latency & Performance Targets** — Define acceptable response time for each component (STT, LLM, TTS, API)
8. **Key Design Decisions** — LLM provider, TTS provider, embedding model, API authentication method

---

## 12. Key Environment Variables (`.env`)

```
SUPABASE_URL=https://<your-project-ref>.supabase.co
SUPABASE_KEY=<your-anon-or-service-role-key>
```

> The migration script (`migrate_to_supabase.py`) and the future `ehr_server.py` both load these via `python-dotenv`.

---

## 13. Design Principles & Constraints

1. **No Medical Advice** — The agent must never diagnose, prescribe, or give clinical recommendations. It routes patients, answers FAQ-level questions, and escalates everything else.
2. **Emergency First** — Emergency keyword detection runs on every single utterance, before any other logic.
3. **HIPAA Awareness** — All data is fake (Synthea-generated). In production, all data must be encrypted in transit (TLS) and at rest. Supabase handles this natively.
4. **Low Latency** — The voice experience is real-time. Every component in the chain (STT → LLM → tool call → TTS) must be optimized for minimal latency.
5. **Graceful Fallback** — If the agent cannot handle a request, it must seamlessly transfer to a human receptionist rather than failing or hallucinating.
6. **Production Architecture** — Design choices mirror real enterprise EHR systems (Epic, Cerner) — relational DB, REST APIs, FHIR standard data formats.
