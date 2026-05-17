# Healthcare Patient Scheduler & Intake Voice Agent

## Overview

This repository contains the architecture and implementation plan for a production-oriented **Healthcare Patient Scheduler & Intake Voice Agent** for Mercy General. The agent acts as an AI receptionist that patients can speak with in real time to handle routine scheduling, intake, FAQ, and routing tasks while reducing front-desk workload.

The project does not rely on static mock responses. It models a realistic hospital environment with a local FastAPI EHR service, FHIR-style synthetic patient data, Supabase/PostgreSQL storage, and a Retrieval-Augmented Generation (RAG) pipeline backed by Supabase Vector / `pgvector`.

The system is designed for scheduling and intake, not diagnosis. Emergency language is handled by a mandatory safety path that interrupts the normal conversation and directs the caller to 911 or the nearest ER.

## Core Agent Features

1. **Smart Appointment Scheduling & Management**
   - Book appointments with specific doctors or departments.
   - Reschedule or cancel existing appointments over the phone.
   - Apply cross-coverage logic when the requested primary care doctor is unavailable.
   - Route ER requests appropriately without trying to schedule an ER slot.

2. **Patient Authentication & Profile Fetching**
   - Verify returning patients using basic identity information such as name, date of birth, and phone number.
   - Fetch a token-efficient patient profile from the EHR API so the agent has relevant context without exposing raw FHIR records to the LLM.

3. **New Patient Onboarding**
   - Move callers who are not found in the EHR into a lightweight registration flow.
   - Create a shell patient profile with only the minimum demographic fields needed to hold an appointment.
   - Use the backend patient creation endpoint so new patients can be scheduled immediately after registration.

4. **Conversational Medical Triage via RAG**
   - Retrieve approved hospital FAQ, policy, department, and symptom-routing content from Supabase Vector.
   - Answer only from curated knowledge base snippets and keep responses scoped to services the hospital actually supports.
   - Use RAG for safe routing and FAQ support, not diagnosis or treatment advice.

5. **Strict Emergency Guardrails**
   - Screen every finalized patient utterance for emergency language such as chest pain, trouble breathing, severe bleeding, or crisis phrases.
   - Stop the normal scheduling flow immediately when the emergency gate triggers.
   - Play a fixed escalation script instructing the caller to dial 911 or go to the nearest ER.

6. **Basic Intake & Insurance Verification**
   - Collect chief complaint, symptom duration, and basic appointment reason.
   - Gather basic insurance provider details for downstream billing context.

## Technology Stack

### Voice and Realtime

- **WebRTC:** Primary v1 transport for low-latency bidirectional audio between the browser client and the realtime gateway.
- **Twilio:** Planned for PSTN telephony; a phone number is **not** currently provisioned, so live calls run over WebRTC instead of the phone network.
- **Deepgram:** Streaming speech-to-text (STT) and text-to-speech (TTS) for the voice pipeline.
- **Realtime gateway:** Signaling, media routing, STT/TTS adapters, session heartbeat, and barge-in.

### AI, Orchestration, and Data

- **LangGraph:** Flow-based conversation orchestrator (outer graph) with tool-calling LLM inside each node; policy, emergency gating, confirmations, and tool allowlists live in the graph—not unconstrained in the LLM.
- **RAG:** Supabase Vector / `pgvector` over curated Mercy General knowledge base files; retrieval tools are invoked from LangGraph nodes (e.g. `RAG_ANSWER`).
- **FastAPI EHR service:** Simulated EHR boundary for patients, providers, appointments, availability, and profile summaries.
- **Supabase/PostgreSQL:** Application data store for EHR-like entities and operational records.
- **FHIR-style synthetic data:** Realistic but fake patient/provider data generated from Synthea.

## Main System Design

The architecture uses a **flow-based outer graph** (LangGraph) for predictable healthcare workflow control and a **tool-calling LLM inside each node** for flexible conversation. The orchestrator, not the LLM, owns policy enforcement, emergency handling, tool allowlists, confirmation checks, and appointment commits.

### High-level context (C4-style)

Patients use a **WebRTC client**. A **realtime gateway** terminates signaling and coordinates media with STT/TTS and the **conversation orchestrator**. The orchestrator calls the **EHR API** (FastAPI) and **RAG service**; persistent state and RAG vectors live in **Supabase**. External providers supply STT, LLM, and TTS.

```mermaid
flowchart TB
  subgraph Patients["Patients"]
    Client["WebRTC client\n(browser / app)"]
  end

  subgraph YourCloud["Your cloud (production boundary)"]
    GW["Realtime gateway\n(signaling + session)"]
    Orch["Conversation orchestrator\n(flow graph + policies)"]
    EHR["EHR API\nFastAPI"]
    RAG["RAG service\n(embed + retrieve)"]
    Vector["Supabase Vector\npgvector"]
    DB[(Supabase\nPostgreSQL)]
  end

  subgraph External["External providers"]
    STT["STT\n(Deepgram)"]
    LLM["LLM provider"]
    TTS["TTS\n(Deepgram)"]
  end

  Client <-->|"WebRTC\n(DTLS-SRTP)"| GW
  GW <-->|"audio / partial text"| STT
  GW <-->|"stream text"| LLM
  GW <-->|"stream audio"| TTS
  Orch <-->|"HTTP / internal RPC"| GW
  Orch --> EHR
  Orch --> RAG
  RAG --> Vector
  EHR --> DB
```

**Trust note:** The orchestrator is the **policy enforcement point** (emergency, confirmations, allowed tools). The LLM never bypasses it for side effects.

### Component responsibilities

| Component | Responsibility |
| --------- | -------------- |
| WebRTC client | Capture/play audio; establish secure session; minimal UX (connect, mute, disconnect, handoff). |
| Realtime gateway | WebRTC signaling; audio routing to STT; subscribe LLM/TTS streams; session heartbeat; backpressure. |
| Conversation orchestrator (LangGraph) | Current graph node, transitions, slot-filling, tool allowlists per node, confirmation tokens, audit events. |
| EHR API | Patient lookup, profile summary, providers, availability, appointments; validates against DB and business rules. |
| RAG service | Embed query, retrieve top-k from Supabase Vector, apply hospital scope filters, return citations/snippets to orchestrator. |
| Supabase | System of record for doctors, patients, profiles, appointments. |
| Supabase Vector / `pgvector` | Vector store over curated hospital knowledge (no raw PHI requirement in MVP dataset). |

### Deployment view (reference)

```mermaid
flowchart LR
  subgraph Edge["Edge / realtime tier"]
    GW2["Realtime gateway"]
  end

  subgraph App["Application tier"]
    Orch2["Orchestrator"]
    EHR2["EHR API"]
    RAG2["RAG service"]
  end

  subgraph Data["Data tier"]
    DB2[(Supabase)]
    Vec2[(Supabase Vector\npgvector)]
  end

  GW2 --> Orch2
  Orch2 --> EHR2
  Orch2 --> RAG2
  EHR2 --> DB2
  RAG2 --> Vec2
```

### Call lifecycle (happy path, simplified)

```mermaid
sequenceDiagram
  participant C as Client
  participant G as Realtime gateway
  participant O as Orchestrator
  participant S as STT
  participant L as LLM
  participant E as EHR API

  C->>G: WebRTC connect
  G->>O: session_start(session_id)
  O->>G: greeting + TTS stream

  loop Each utterance
    C->>G: audio frames
    G->>S: stream audio
    S-->>G: partial/final transcript
    G->>O: transcript_event(text, is_final)
    O->>O: emergency_gate(text)
    alt emergency
      O->>G: play_911_script + end_session
    else normal
      O->>L: node_prompt + tools (stream)
      L-->>O: tokens / tool_calls
      O->>E: tool HTTP (when allowed)
      E-->>O: structured result
      O->>G: assistant_text stream to TTS
    end
  end
```

### Safety and trust guarantees

- **Emergency-first:** emergency screening runs before regular scheduling or FAQ behavior.
- **No diagnosis:** the system provides intake, routing, and FAQ responses, not clinical diagnosis, prescriptions, or definitive treatment advice.
- **Deterministic commits:** appointment mutations require explicit confirmation and idempotent EHR API writes.
- **Least-data LLM context:** raw FHIR records stay behind the EHR boundary; the LLM receives minimized summaries only.
- **Human handoff:** repeated failures, user requests, out-of-scope clinical demands, or backend errors can route to staff.
- **Auditable behavior:** key events such as verification, availability shown, appointment committed, emergency triggered, and handoff are logged in structured form without unnecessary PHI.

---

## Voice and Realtime Layer

From [`system design/02-component-voice-realtime.md`](system%20design/02-component-voice-realtime.md).

### Reference topology

```mermaid
flowchart TB
  subgraph Client["Patient device"]
    Mic["Microphone"]
    Spk["Speaker"]
    PC["WebRTC PeerConnection"]
  end

  subgraph Gateway["Realtime gateway"]
    Sig["Signaling handler"]
    Med["Media bridge\n(or SFU peer)"]
    STTIn["STT adapter"]
    TTSOut["TTS adapter"]
    Bus["Internal event bus\n(transcript / assistant_delta)"]
  end

  Mic --> PC
  PC <-->|"DTLS-SRTP"| Med
  Med --> STTIn
  TTSOut --> Med
  Med --> Spk
  Sig --- PC
  STTIn --> Bus
  Bus --> Orch["Orchestrator"]
  Orch --> Bus
  Bus --> TTSOut
```

### Latency budget (planning targets)

```mermaid
flowchart LR
  A["Audio frame"] --> B["STT partial/final"]
  B --> C["Orchestrator + LLM\n(first token)"]
  C --> D["TTS\n(first audio)"]
  D --> E["Playback"]
```

| Stage | Target (order of magnitude) | Mitigation |
| ----- | --------------------------- | ---------- |
| STT | ~150–300 ms to useful text | Streaming API; region proximity |
| Policy + LLM | first token ~200–500 ms | Small node prompts; tool-only turns |
| TTS | first audio ~150–300 ms | Streamed synthesis; cache common phrases |
| **End-to-end** | **minimize silence** | Overlap stages; barge-in; pre-roll greetings |

---

## Conversation Orchestration (LangGraph)

From [`system design/03-component-orchestration.md`](system%20design/03-component-orchestration.md).

### Outer graph (simplified)

```mermaid
flowchart TB
  START([session_start]) --> E0[EMERGENCY_GATE]

  E0 -->|cleared| ID[PATIENT_IDENTIFY]
  E0 -->|triggered| EM[PLAY_911_SCRIPT]
  EM --> END_EM([end_session])

  ID -->|returning| AUTH[VERIFY_RETURNING]
  ID -->|new| REG[REGISTER_SHELL_PROFILE]

  AUTH --> ROUTE[CLINICAL_ROUTE]
  REG --> ROUTE

  ROUTE --> SCH[SCHEDULING]
  SCH --> CONF[CONFIRM_COMMIT]
  CONF --> INTAKE[INSURANCE_INTAKE]
  INTAKE --> DONE([wrap_up])

  ROUTE -->|FAQ/triage| RAG_NODE[RAG_ANSWER]
  RAG_NODE --> ROUTE
```

### Emergency gate (explicit FSM)

```mermaid
stateDiagram-v2
  [*] --> CheckText: new_final_transcript
  CheckText --> Emergency: keyword_or_classifier_hit
  CheckText --> Normal: no_hit
  Emergency --> [*]: play_script_and_terminate
  Normal --> [*]: proceed_to_graph
```

### Inner loop inside a node (LLM + tools)

Example: `SCHEDULING` node.

```mermaid
sequenceDiagram
  participant O as Orchestrator
  participant L as LLM
  participant E as EHR API

  O->>L: system+node prompt, user text, allowed_tools
  L-->>O: tool_call get_availability(...)
  O->>O: validate tool allowed in SCHEDULING
  O->>E: GET availability
  E-->>O: slots JSON
  O->>L: tool_result
  L-->>O: propose_slot + ask_confirm
  O->>O: move to CONFIRM_COMMIT only if UX rules satisfied
```

### Human handoff

```mermaid
flowchart LR
  H[User or policy trigger] --> T{handoff_reason}
  T --> Q[queue_staff_queue]
  T --> N[notify_on-call]
  Q --> END[Close AI session gracefully]
```

---

## Backend EHR Service

From [`system design/04-component-backend-ehr.md`](system%20design/04-component-backend-ehr.md).

### Placement in the architecture

```mermaid
flowchart LR
  Orch["Orchestrator"] --> API["EHR API\nFastAPI"]
  API --> DB[(Supabase)]
  API --> Cache["Optional cache\n(short TTL)"]
```

### Cross-coverage and scheduling rules

```mermaid
flowchart TB
  REQ[availability_request] --> DEPT{department_policy}
  DEPT -->|Primary Care| ALT[offer alternate PCP in dept]
  DEPT -->|ER| WALK[return walk_in_instruction\nno slots]
  DEPT -->|Specialist| CONT[continuity rules\nlimited cross-cover]
```

---

## Data Layer and RAG

From [`system design/05-component-data-rag.md`](system%20design/05-component-data-rag.md).

### Supabase logical model

```mermaid
erDiagram
  doctors ||--o{ appointments : has
  patients ||--o{ appointments : has
  patients ||--|| medical_profiles : has
  doctors {
    uuid id PK
    string specialty
    json raw_fhir_data
  }
  patients {
    uuid id PK
    string phone
    date dob
  }
  medical_profiles {
    uuid patient_id PK
    json clinical_data
  }
  appointments {
    uuid id PK
    uuid patient_id FK
    uuid doctor_id FK
    timestamp appointment_time
    string status
    string reason
  }
```

### Read paths vs LLM context

```mermaid
flowchart TB
  DB[(Supabase)] --> EHR["EHR API"]
  EHR --> O["Orchestrator"]
  O --> L["LLM\n(minimized JSON)"]
```

### RAG pipeline

```mermaid
flowchart LR
  Q["User question\n(or symptoms phrase)"] --> E["Embed query"]
  E --> C["Supabase Vector\npgvector similarity search"]
  C --> F["Filter + hospital scope"]
  F --> R["Top-k chunks +\nsource ids"]
  R --> O2["Orchestrator"]
  O2 --> L2["LLM: answer from\ncitations only"]
```

---

## Trust, Security, and Operations

From [`system design/06-trust-security-operations.md`](system%20design/06-trust-security-operations.md).

### Safety-critical paths (must never regress)

```mermaid
flowchart TB
  E[Emergency gate] -->|highest priority| A[911 script + session end]
  C[Booking commit] -->|requires| B[human confirmation + idempotency]
  H[Handoff] -->|always available| D[staff queue / callback]
```

---

## Project Structure

- `data/`: Seed data and curated RAG knowledge.
  - `fhir/`: Realistic mock patient and provider JSON bundles from Synthea.
  - `healthcare_qa.csv`: Legacy tiny medical Q&A dataset kept for reference.
  - `knowledge_base/`: Primary RAG source for Mercy General policy, department services, FAQ, appointment prep, and safe care routing.
- `docs/`: Product and feature documentation, including `docs/features.md`.
- `scripts/`: Utility scripts for downloading datasets, models, and preparing Supabase/RAG assets.
- `system design/`: Source architecture documents for the main design and component-level design.
- `Rag Evaluation/`: Placeholder area for RAG quality and retrieval evaluation work.

## System Design Documents

Start with the main design, then read the component documents in order:

1. [`system design/01-main-system-design.md`](system%20design/01-main-system-design.md) - end-to-end architecture, deployment view, call lifecycle sequence, and trust principles.
2. [`system design/02-component-voice-realtime.md`](system%20design/02-component-voice-realtime.md) - WebRTC, signaling, media, STT/TTS streaming, latency, and barge-in.
3. [`system design/03-component-orchestration.md`](system%20design/03-component-orchestration.md) - flow graph, emergency gate, tool allowlists, confirmations, and handoff.
4. [`system design/04-component-backend-ehr.md`](system%20design/04-component-backend-ehr.md) - FastAPI EHR service responsibilities, endpoint map, validation, and errors.
5. [`system design/05-component-data-rag.md`](system%20design/05-component-data-rag.md) - Supabase schema, RAG ingestion/retrieval, privacy, and rollback.
6. [`system design/06-trust-security-operations.md`](system%20design/06-trust-security-operations.md) - security posture, audit events, SLOs, incidents, and customer-facing assurances.

## Setup & Installation

1. **Clone the repository and navigate to the directory:**

   ```bash
   cd "MedCall-AI"
   ```

2. **Set up a Python virtual environment:**

   ```bash
   python -m venv venv

   # Windows
   .\venv\Scripts\activate

   # macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Acquire seed data:**

   ```bash
   python scripts/download_qa_data.py
   python scripts/download_synthea_data.py
   ```

5. **Prepare the local RAG/vector assets as needed:**

   ```bash
   python scripts/download_embedding_model.py
   ```

   The Supabase vector database setup is documented in `scripts/supabase_rag_vector_db.sql`.

   Set `DEEPGRAM_API_KEY` (and other env vars) in `.env` for STT/TTS. See `src/config.py` for optional `TTS_PROVIDER` overrides.

## Current Status

- **Phase 1 complete:** Seed data acquisition is complete, and the curated Mercy General policy knowledge base is available under `data/knowledge_base/`.
- **Phase 2 in progress:** Building the local EHR service and Supabase Vector RAG pipeline so the voice agent can make live API queries during patient calls.
- **Voice layer in progress:** WebRTC gateway with Deepgram STT/TTS adapters; LangGraph orchestrator and full tool integration remain in progress.
- **Architecture baseline complete:** The main system design and component documents define the WebRTC transport, LangGraph orchestration, EHR API boundary, RAG pipeline, and production trust posture.
