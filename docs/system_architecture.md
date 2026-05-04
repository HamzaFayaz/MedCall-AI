# System Architecture — Healthcare Voice Agent
**Version:** 1.0 | **Last Updated:** May 4, 2026 | **Phase 5 Deliverable**

> This document defines the complete system architecture. Part 1 covers the high-level view. Part 2 (`component_architectures.md`) covers each component in detail.

---

## 1. Architecture Overview

The system uses a **State Machine pattern** (LangGraph) as the orchestration brain, with **WebRTC** for real-time browser-to-server audio, **Deepgram** for STT/TTS, and **FastAPI** as the EHR backend connecting to **Supabase**.

### Cloud-Agnostic Design
The entire system is deployable on **any cloud platform**:

| Component | Google Cloud | AWS | Azure | Local Dev |
|---|---|---|---|---|
| Backend Server | Cloud Run | ECS / Lambda | Container Apps | `uvicorn` |
| WebRTC Signaling | Cloud Run | ECS | Container Apps | `localhost` |
| Database | Supabase (external) | Supabase (external) | Supabase (external) | Supabase (external) |
| Vector DB | ChromaDB on server | ChromaDB on server | ChromaDB on server | ChromaDB local |
| STT/TTS | Deepgram (external API) | Deepgram (external API) | Deepgram (external API) | Deepgram (external API) |
| LLM | Google Gemini / OpenAI | OpenAI / Anthropic | OpenAI / Anthropic | Any via API key |

> **Supabase** and **Deepgram** are external SaaS — they work identically regardless of where your server is hosted.

---

## 2. High-Level System Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         PATIENT'S BROWSER                              │
│                                                                         │
│   ┌──────────────┐     ┌──────────────┐     ┌────────────────────┐     │
│   │  Microphone   │────►│  WebRTC      │────►│  WebSocket to      │     │
│   │  (Audio In)   │     │  Client JS   │     │  Backend Server    │     │
│   └──────────────┘     └──────────────┘     └────────┬───────────┘     │
│   ┌──────────────┐                                    │                 │
│   │  Speaker      │◄── TTS Audio Stream ──────────────┤                 │
│   │  (Audio Out)  │                                    │                 │
│   └──────────────┘                                    │                 │
└───────────────────────────────────────────────────────┼─────────────────┘
                                                        │
                                    WebSocket (binary audio + JSON messages)
                                                        │
┌───────────────────────────────────────────────────────┼─────────────────┐
│                      BACKEND SERVER (FastAPI)          │                 │
│                                                        ▼                 │
│   ┌────────────────────────────────────────────────────────────┐        │
│   │              WebSocket Handler (voice_server.py)           │        │
│   │  Receives audio stream from browser, manages session      │        │
│   └─────────┬──────────────────────────────────────┬──────────┘        │
│             │                                      │                    │
│             ▼                                      ▼                    │
│   ┌─────────────────┐                   ┌─────────────────────┐        │
│   │   Deepgram STT   │                   │   Deepgram TTS      │        │
│   │   (Streaming)    │                   │   (Text → Audio)    │        │
│   │   Audio → Text   │                   │   Reply → Speaker   │        │
│   └────────┬────────┘                   └──────────▲──────────┘        │
│            │ transcript                             │ LLM response      │
│            ▼                                        │                    │
│   ┌────────────────────────────────────────────────────────────┐        │
│   │           LangGraph State Machine (agent_graph.py)         │        │
│   │                                                            │        │
│   │  ┌──────────────────────────────────────────────────┐     │        │
│   │  │  GLOBAL EDGE: Emergency Detector                  │     │        │
│   │  │  Fires on EVERY utterance before any node runs    │     │        │
│   │  └──────────────────────────────────────────────────┘     │        │
│   │                                                            │        │
│   │  [AUTH] ──► [ROUTING] ──► [SCHEDULING] ──► [CONFIRM]      │        │
│   │    │           │              │                             │        │
│   │    └─[NEW PT]  └─[FAQ/RAG]   └─[CROSS-COVERAGE]          │        │
│   │                                                            │        │
│   │  State Object: { patient_id, clinical_data, intent,       │        │
│   │                   booking_slot, is_emergency, ... }        │        │
│   └──────────────┬─────────────────────────────────────────────┘        │
│                  │ tool calls                                           │
│                  ▼                                                       │
│   ┌─────────────────────────────────────────────────────────────┐       │
│   │                  EHR API Layer (ehr_server.py)               │       │
│   │                                                              │       │
│   │  /patients      — lookup, create, authenticate              │       │
│   │  /providers     — search by name, specialty, availability   │       │
│   │  /appointments  — book, cancel, reschedule, list            │       │
│   │  /triage        — RAG query to ChromaDB                     │       │
│   └──────────┬──────────────────────────────┬───────────────────┘       │
│              │                              │                            │
│              ▼                              ▼                            │
│   ┌──────────────────┐          ┌──────────────────────┐                │
│   │   Supabase        │          │   ChromaDB            │                │
│   │   (PostgreSQL)    │          │   (Vector Store)      │                │
│   │                   │          │                       │                │
│   │  doctors          │          │  healthcare_qa        │                │
│   │  patients         │          │  collection           │                │
│   │  medical_profiles │          │  (embeddings from     │                │
│   │  appointments     │          │   healthcare_qa.csv)  │                │
│   └──────────────────┘          └──────────────────────┘                │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Data Flow — Full Call Lifecycle

### Sequence: Patient calls to book an appointment

```
Patient Browser          WebSocket Handler       Deepgram        LangGraph          EHR API          Supabase
     │                         │                    │                │                  │                │
     │── Audio stream ────────►│                    │                │                  │                │
     │                         │── Audio chunks ──►│                │                  │                │
     │                         │                    │── transcript ─►│                  │                │
     │                         │                    │                │                  │                │
     │                         │                    │    [EMERGENCY CHECK — no trigger] │                │
     │                         │                    │                │                  │                │
     │                         │                    │    [AUTH NODE]  │                  │                │
     │                         │                    │    LLM: "What  │                  │                │
     │                         │                    │    is your name│                  │                │
     │                         │                    │    and DOB?"   │                  │                │
     │                         │                    │                │                  │                │
     │                         │◄─ TTS audio ──────│◄─ LLM text ───│                  │                │
     │◄── Audio response ─────│                    │                │                  │                │
     │                         │                    │                │                  │                │
     │── "John Smith, March 12"│                    │                │                  │                │
     │                         │── Audio ─────────►│── transcript ─►│                  │                │
     │                         │                    │                │──lookup_patient()►│── SQL query ──►│
     │                         │                    │                │◄─ patient data ──│◄── result ────│
     │                         │                    │                │                  │                │
     │                         │                    │    State fills: patient_id,       │                │
     │                         │                    │    clinical_data                  │                │
     │                         │                    │                │                  │                │
     │                         │                    │    [ROUTING NODE]                 │                │
     │                         │                    │    LLM: "What is the reason       │                │
     │                         │                    │    for your visit?"               │                │
     │                         │                    │                │                  │                │
     │── "I need to see a      │                    │                │                  │                │
     │    cardiologist"         │                    │                │                  │                │
     │                         │                    │── transcript ─►│                  │                │
     │                         │                    │                │──get_providers()─►│── SQL query ──►│
     │                         │                    │                │◄─ available docs ─│◄── result ────│
     │                         │                    │                │                  │                │
     │                         │                    │    [SCHEDULING NODE]              │                │
     │                         │                    │    LLM: "Dr. Rostova has          │                │
     │                         │                    │    openings Mon 10AM, Tue 2PM"    │                │
     │                         │                    │                │                  │                │
     │── "Monday at 10 works"  │                    │                │                  │                │
     │                         │                    │── transcript ─►│                  │                │
     │                         │                    │                │──book_appt()────►│── INSERT ────►│
     │                         │                    │                │◄─ confirmation ──│◄── result ────│
     │                         │                    │                │                  │                │
     │                         │                    │    [CONFIRM NODE]                 │                │
     │                         │◄─ TTS audio ──────│◄─ LLM text ───│                  │                │
     │◄── "Your appointment is │                    │                │                  │                │
     │     confirmed for..."   │                    │                │                  │                │
     │                         │                    │                │                  │                │
     │── [END CALL] ──────────►│                    │                │                  │                │
```

---

## 4. Component Inventory

| # | Component | File(s) | Tech | Responsibility |
|---|---|---|---|---|
| 1 | **WebRTC Client** | `frontend/index.html`, `frontend/app.js` | HTML + JS + WebRTC API | Captures mic audio, sends via WebSocket, plays TTS audio |
| 2 | **Voice Server** | `voice_server.py` | FastAPI + WebSockets | Bridges browser audio ↔ Deepgram ↔ LangGraph |
| 3 | **STT Service** | Deepgram Streaming API | External SaaS | Real-time audio → text transcription |
| 4 | **TTS Service** | Deepgram TTS API | External SaaS | Text → natural speech audio |
| 5 | **Agent Brain** | `agent_graph.py` | LangGraph + LLM | State machine: auth → routing → scheduling → confirm |
| 6 | **EHR API** | `ehr_server.py` | FastAPI | REST endpoints for patients, providers, appointments |
| 7 | **RAG Pipeline** | `rag_pipeline.py` | ChromaDB + Embeddings | Medical Q&A semantic search |
| 8 | **Database** | Supabase | PostgreSQL + JSONB | 4 tables: doctors, patients, medical_profiles, appointments |

---

## 5. LangGraph State Machine — Detailed Design

### 5.1 State Object

```python
class CallState(TypedDict):
    # Session
    session_id:      str              # Unique call ID
    current_node:    str              # Which state we're in

    # Audio Pipeline
    transcript:      str              # Latest patient utterance from Deepgram
    full_history:    list[dict]       # [{role: "patient"/"agent", text: "..."}]

    # Emergency
    is_emergency:    bool             # Set by emergency detector

    # Patient Data (filled in AUTH node)
    patient_id:      str | None       # UUID from Supabase
    patient_name:    str | None
    patient_dob:     str | None
    clinical_data:   dict | None      # Full clinical_data JSONB from medical_profiles
    is_new_patient:  bool

    # Routing (filled in ROUTING node)
    intent:          str | None       # "schedule" / "cancel" / "reschedule" / "faq"
    target_specialty:str | None       # "Cardiology", "Family Medicine", etc.
    target_doctor:   str | None       # Specific doctor name if requested
    referral_status: str | None       # "has_referral" / "needs_referral" / "not_required"
    symptoms:        str | None       # Patient's stated symptoms

    # Scheduling (filled in SCHEDULING node)
    available_slots: list[dict]       # [{doctor, time, room}]
    booked_slot:     dict | None      # {doctor_id, doctor_name, time, room}

    # Insurance (filled in INTAKE node)
    insurance_provider: str | None
```

### 5.2 Node Definitions

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    LANGGRAPH STATE MACHINE                              │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │  🚨 EMERGENCY EDGE (Global Conditional — checked EVERY turn)   │    │
│  │                                                                │    │
│  │  Input:  state.transcript                                      │    │
│  │  Logic:  keyword match against emergency trigger list          │    │
│  │  Output: if triggered → jump to EMERGENCY_NODE                 │    │
│  │          if not → continue to current node                     │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  ┌──────────┐    ┌───────────┐    ┌──────────────┐    ┌──────────┐    │
│  │  AUTH     │───►│ ROUTING   │───►│ SCHEDULING   │───►│ CONFIRM  │    │
│  │  NODE     │    │ NODE      │    │ NODE         │    │ NODE     │    │
│  └────┬─────┘    └─────┬─────┘    └──────┬───────┘    └──────────┘    │
│       │                │                  │                             │
│       ▼                ▼                  ▼                             │
│  ┌──────────┐    ┌───────────┐    ┌──────────────┐                    │
│  │ NEW      │    │ FAQ/RAG   │    │ CROSS-       │                    │
│  │ PATIENT  │    │ NODE      │    │ COVERAGE     │                    │
│  │ NODE     │    │           │    │ NODE         │                    │
│  └──────────┘    └───────────┘    └──────────────┘                    │
│                                                                         │
│  ┌──────────┐                                                          │
│  │EMERGENCY │  ← terminates call, plays 911 script                    │
│  │NODE      │                                                          │
│  └──────────┘                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.3 Node Responsibilities

| Node | LLM Prompt Focus | Tools Available | Next Edge |
|---|---|---|---|
| **AUTH** | Ask name + DOB; verify identity | `lookup_patient(name, dob)` | found → ROUTING, not found → NEW_PATIENT |
| **NEW_PATIENT** | Collect: name, DOB, phone, gender, insurance | `create_patient(data)` | created → ROUTING |
| **ROUTING** | Ask reason for visit; determine specialty | `search_rag(symptoms)`, `check_referral_policy(specialty)` | schedule → SCHEDULING, faq → FAQ_NODE |
| **FAQ_NODE** | Answer general medical/clinic questions | `search_rag(question)` | answered → ROUTING (loop) or END |
| **SCHEDULING** | Propose slots; handle selection | `get_availability(specialty)`, `book_appointment(...)` | booked → CONFIRM, no slots → CROSS_COVERAGE |
| **CROSS_COVERAGE** | Offer alternative doctor in same dept | `get_availability(specialty, exclude_doctor)` | accepted → CONFIRM |
| **CONFIRM** | Read back appointment details | `send_confirmation(phone, details)` | → END |
| **EMERGENCY** | Play 911 script | `terminate_call()` | → END (immediate) |

### 5.4 Edge Logic (Routing Rules)

```python
# After AUTH node
def route_after_auth(state: CallState) -> str:
    if state["patient_id"]:
        return "routing_node"
    return "new_patient_node"

# After ROUTING node
def route_after_routing(state: CallState) -> str:
    if state["intent"] == "faq":
        return "faq_node"
    if state["referral_status"] == "needs_referral":
        # LLM explains referral policy, loops back
        return "routing_node"
    return "scheduling_node"

# After SCHEDULING node
def route_after_scheduling(state: CallState) -> str:
    if state["booked_slot"]:
        return "confirm_node"
    return "cross_coverage_node"

# GLOBAL — runs before every node
def emergency_check(state: CallState) -> str:
    TRIGGERS = ["chest pain", "can't breathe", "difficulty breathing",
                "severe bleeding", "suicidal", "drooping face",
                "sudden weakness", "shortness of breath"]
    text = state["transcript"].lower()
    if any(trigger in text for trigger in TRIGGERS):
        return "emergency_node"
    return "continue"
```

---

## 6. EHR API Design (`ehr_server.py`)

### 6.1 Endpoint Contract

| Method | Endpoint | Purpose | Request | Response |
|---|---|---|---|---|
| `GET` | `/api/patients/search` | Auth lookup | `?name=John+Smith&dob=1985-03-12` | `{ patient, clinical_data }` |
| `POST` | `/api/patients` | Create new patient | `{ first_name, last_name, dob, phone, gender }` | `{ patient_id, mrn }` |
| `GET` | `/api/patients/{id}/profile` | Full clinical profile | — | `{ patient, clinical_data }` |
| `GET` | `/api/providers` | Search doctors | `?name=Peterson` or `?specialty=Cardiology` | `[{ doctor }]` |
| `GET` | `/api/providers/availability` | Available slots | `?specialty=Cardiology&exclude_doctor=uuid` | `[{ doctor, slots[] }]` |
| `POST` | `/api/appointments` | Book appointment | `{ patient_id, doctor_id, time, reason }` | `{ appointment_id, status }` |
| `PUT` | `/api/appointments/{id}` | Reschedule/cancel | `{ new_time }` or `{ status: "canceled" }` | `{ appointment }` |
| `GET` | `/api/appointments` | List patient appts | `?patient_id=uuid` | `[{ appointment }]` |
| `POST` | `/api/triage` | RAG query | `{ question: "symptoms text" }` | `{ answer, sources[] }` |

### 6.2 Internal Architecture

```
ehr_server.py (FastAPI)
│
├── /api/patients/*     ──► supabase_client.table("patients")
├── /api/providers/*    ──► supabase_client.table("doctors")
├── /api/appointments/* ──► supabase_client.table("appointments")
└── /api/triage         ──► chromadb_collection.query(embedding)
```

---

## 7. RAG Pipeline Design (`rag_pipeline.py`)

### 7.1 Ingestion (One-Time Setup)

```
healthcare_qa.csv ──► Chunk each Q&A pair
                       ──► Generate embeddings (sentence-transformers)
                       ──► Store in ChromaDB collection "healthcare_qa"
```

### 7.2 Query (Runtime)

```
Patient says symptoms ──► Embed the query
                          ──► ChromaDB similarity search (top 3)
                          ──► Return matched Q&A pairs as LLM context
```

### 7.3 Tech Choices

| Choice | Selected | Rationale |
|---|---|---|
| **Vector DB** | ChromaDB (local/persistent) | Free, no cloud dependency, fast for <10K docs |
| **Embedding Model** | `all-MiniLM-L6-v2` (sentence-transformers) | Fast, 384-dim, great for medical text, runs on CPU |
| **Collection** | `healthcare_qa` | One collection, each doc = one Q&A pair |
| **Search** | Cosine similarity, top 3 results | Enough context for triage without token bloat |

---

## 8. WebRTC Client Architecture

### 8.1 Browser-Side Components

```
frontend/
├── index.html        ← UI: call button, status indicator, transcript display
├── app.js            ← WebRTC logic: mic capture, WebSocket connection
└── styles.css        ← Call interface styling
```

### 8.2 Audio Flow

```
Browser Microphone
    │
    ▼
MediaStream API (getUserMedia)
    │
    ▼
AudioWorklet / MediaRecorder
    │ (PCM or Opus audio chunks)
    ▼
WebSocket.send(audioBlob)  ────►  voice_server.py
                                       │
                            Deepgram streaming STT ──► transcript
                                       │
                            LangGraph processes ──► LLM response text
                                       │
                            Deepgram TTS ──► audio bytes
                                       │
                            WebSocket.send(audioReply) ──► Browser
                                                              │
                                                         AudioContext.play()
                                                              │
                                                           Speaker 🔊
```

### 8.3 WebSocket Message Protocol

```json
// Client → Server: Audio chunk
{ "type": "audio", "data": "<base64 encoded audio>" }

// Client → Server: Control
{ "type": "start_call" }
{ "type": "end_call" }

// Server → Client: Agent response audio
{ "type": "audio_response", "data": "<base64 encoded audio>" }

// Server → Client: Transcript (for UI display)
{ "type": "transcript", "role": "patient", "text": "I need to see a doctor" }
{ "type": "transcript", "role": "agent", "text": "What is your name?" }

// Server → Client: Status updates
{ "type": "status", "state": "listening" | "thinking" | "speaking" }

// Server → Client: Emergency termination
{ "type": "emergency", "message": "Please call 911 immediately." }
```

---

## 9. Voice Server Architecture (`voice_server.py`)

The central orchestrator that bridges all components:

```python
# voice_server.py — Simplified Architecture

@app.websocket("/ws/call")
async def call_handler(websocket: WebSocket):
    # 1. Accept WebSocket connection from browser
    await websocket.accept()
    session_id = uuid4()

    # 2. Open streaming connection to Deepgram STT
    deepgram_ws = await connect_deepgram_streaming()

    # 3. Initialize LangGraph with empty state
    graph_state = CallState(session_id=session_id, ...)
    graph = build_agent_graph()

    # 4. Main loop
    async for message in websocket:
        if message.type == "audio":
            # Forward audio to Deepgram
            await deepgram_ws.send(message.data)

        # When Deepgram returns a transcript:
        transcript = await deepgram_ws.receive_transcript()
        graph_state["transcript"] = transcript

        # Run the LangGraph state machine
        result = await graph.ainvoke(graph_state)
        llm_response = result["agent_response"]

        # Convert LLM text to speech via Deepgram TTS
        audio = await deepgram_tts(llm_response)

        # Send audio back to browser
        await websocket.send(audio)
```

---

## 10. File Structure (After Phase 6 Build)

```
Voice Agent/
├── PRD.md
├── docs/
│   ├── system_architecture.md          ← THIS FILE
│   ├── component_architectures.md      ← Detailed per-component specs
│   ├── project_plan.md
│   └── ... (existing docs)
│
├── frontend/                           ← NEW: WebRTC Client
│   ├── index.html
│   ├── app.js
│   └── styles.css
│
├── src/                                ← NEW: Backend Application Code
│   ├── voice_server.py                 ← WebSocket handler (main entry)
│   ├── agent_graph.py                  ← LangGraph state machine
│   ├── ehr_server.py                   ← FastAPI EHR REST API
│   ├── rag_pipeline.py                 ← ChromaDB ingestion + query
│   ├── tools/                          ← LangGraph tool functions
│   │   ├── patient_tools.py            ← lookup_patient, create_patient
│   │   ├── provider_tools.py           ← search_providers, get_availability
│   │   ├── appointment_tools.py        ← book, cancel, reschedule
│   │   └── triage_tools.py             ← search_rag
│   ├── prompts/                        ← LLM system prompts per node
│   │   ├── auth_prompt.py
│   │   ├── routing_prompt.py
│   │   ├── scheduling_prompt.py
│   │   └── emergency_prompt.py
│   └── config.py                       ← Environment vars, constants
│
├── data/                               ← Existing seed data
├── scripts/                            ← Existing migration scripts
└── requirements.txt                    ← Updated with new deps
```

---

## 11. Latency Budget

Real-time voice requires total round-trip under **2 seconds**:

| Step | Target | Technology |
|---|---|---|
| Audio capture + WebSocket send | ~50ms | Browser WebRTC |
| Speech-to-Text | ~300ms | Deepgram Streaming (interim results) |
| LangGraph node + LLM call | ~800ms | GPT-4o-mini or Gemini Flash |
| Tool call (EHR API → Supabase) | ~200ms | FastAPI + Supabase REST |
| Text-to-Speech | ~300ms | Deepgram TTS (streaming) |
| Audio playback | ~50ms | Browser AudioContext |
| **Total** | **~1.7s** | — |

> **Key optimization:** Use streaming for both STT and TTS. The LLM can start generating while Deepgram is still finishing transcription, and TTS can start playing the first sentence while the LLM is still generating the rest.

---

## 12. Required API Keys & Environment

```env
# .env file
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_KEY=<service-role-key>
DEEPGRAM_API_KEY=<deepgram-key>
OPENAI_API_KEY=<openai-key>          # or GOOGLE_API_KEY for Gemini
CHROMADB_PATH=./data/chromadb         # local persistent path
```

---

## 13. Dependency List (New for Phase 6)

```
# requirements.txt additions
fastapi
uvicorn[standard]
websockets
langgraph
langchain-core
langchain-openai          # or langchain-google-genai
deepgram-sdk
chromadb
sentence-transformers
supabase
python-dotenv
```

---

## Next Steps

1. ✅ You are here: `system_architecture.md` (high-level architecture complete)
2. → Create `component_architectures.md` (detailed specs for each component)
3. → Update `PRD.md` with finalized tech stack
4. → Begin Phase 6: Build each component following this blueprint
