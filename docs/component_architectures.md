# Component Architectures — Healthcare Voice Agent
**Version:** 1.0 | **Last Updated:** May 4, 2026 | **Phase 5 Deliverable — Part 2**

> This document drills into each component from `system_architecture.md`. Each section is self-contained — a developer can read one section and build that component independently.

---

## Component 1: WebRTC Client (`frontend/`)

### Purpose
A browser-based UI that lets a patient "call" the voice agent by clicking a button. It captures microphone audio, streams it to the backend over a WebSocket, and plays back the agent's spoken responses.

### File Structure
```
frontend/
├── index.html        ← Call interface UI
├── app.js            ← WebSocket + Audio logic
└── styles.css        ← Styling
```

### UI Layout
```
┌──────────────────────────────────────────────────┐
│         Mercy General Hospital                    │
│         AI Patient Assistant                      │
│                                                   │
│              ┌──────────────┐                     │
│              │   📞 CALL    │  ← Big call button  │
│              │              │     (toggles to     │
│              │              │      🔴 END CALL)   │
│              └──────────────┘                     │
│                                                   │
│  Status: 🟢 Connected / Listening / Speaking      │
│                                                   │
│  ┌─────────────────────────────────────────────┐  │
│  │  Live Transcript                             │  │
│  │                                              │  │
│  │  Agent: Hello, you've reached Mercy General  │  │
│  │  You:   I need to schedule an appointment    │  │
│  │  Agent: Of course! What is your full name?   │  │
│  └─────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

### `app.js` — Core Logic Flow

```
1. User clicks "CALL" button
       │
2. getUserMedia({ audio: true })  ← request mic permission
       │
3. Open WebSocket to ws://backend:8000/ws/call
       │
4. Create AudioWorklet to capture PCM audio chunks
       │
5. LOOP: every ~100ms
   ├── Capture audio chunk from mic
   ├── Send as binary WebSocket message → backend
   │
   └── Receive messages from backend:
       ├── "audio_response" → decode + play via AudioContext
       ├── "transcript"     → append to transcript div
       ├── "status"         → update status indicator
       └── "emergency"      → show red banner, auto-disconnect
       
6. User clicks "END CALL" → send { type: "end_call" } → close WebSocket
```

### Audio Configuration
| Setting | Value | Rationale |
|---|---|---|
| Sample Rate | 16000 Hz | Deepgram's optimal input rate |
| Channels | 1 (mono) | Voice doesn't need stereo |
| Encoding | Linear16 (PCM) | Deepgram's preferred format for streaming |
| Chunk Size | 100ms (~1600 samples) | Low latency without overwhelming the WebSocket |

---

## Component 2: Voice Server (`src/voice_server.py`)

### Purpose
The central hub. It runs as a FastAPI server that:
- Accepts WebSocket connections from the browser
- Streams audio to Deepgram for transcription
- Feeds transcripts into the LangGraph agent
- Converts LLM responses to speech via Deepgram TTS
- Streams audio responses back to the browser

### Internal Architecture

```
voice_server.py
│
├── FastAPI app
│   ├── WebSocket endpoint: /ws/call
│   └── REST endpoints: /api/* (mounted from ehr_server.py)
│
├── CallSession class (one per active call)
│   ├── session_id: UUID
│   ├── websocket: WebSocket connection to browser
│   ├── deepgram_stt: Streaming STT connection
│   ├── deepgram_tts: TTS client
│   ├── graph_runner: LangGraph instance
│   └── state: CallState object
│
└── Main WebSocket handler
    ├── on_connect: create CallSession
    ├── on_audio: forward to Deepgram STT
    ├── on_transcript: run LangGraph → get response → TTS → send audio
    └── on_disconnect: cleanup session
```

### Concurrency Model

```
Per WebSocket connection, 3 async tasks run concurrently:

Task 1: Audio Receiver
  └── Reads binary audio from browser WebSocket → forwards to Deepgram STT

Task 2: Transcript Processor
  └── Listens for Deepgram transcription results
      └── On final transcript → runs LangGraph → sends response

Task 3: TTS Streamer
  └── Takes LLM text response → calls Deepgram TTS → streams audio back to browser
```

### Key Design Decisions
| Decision | Choice | Rationale |
|---|---|---|
| Single server vs. separate servers | **Single FastAPI server** | Simpler deployment; EHR API endpoints are just additional routes on the same server |
| Session management | **In-memory dict** `{session_id: CallSession}` | Sufficient for demo scale; production would use Redis |
| Deepgram connection | **One persistent streaming connection per call** | Avoids reconnection latency on every utterance |

---

## Component 3: Deepgram Integration (STT + TTS)

### STT — Speech-to-Text (Streaming)

```
Browser Audio ──► voice_server.py ──► Deepgram WebSocket API
                                            │
                                    Returns: interim + final transcripts
                                            │
                                    On "is_final" transcript ──► LangGraph
```

**Configuration:**
```python
deepgram_options = {
    "model": "nova-2",           # Best accuracy model
    "language": "en-US",
    "smart_format": True,        # Adds punctuation
    "interim_results": True,     # Show partial text while speaking
    "utterance_end_ms": 1000,    # Silence threshold = 1 second
    "vad_events": True,          # Voice Activity Detection
    "encoding": "linear16",
    "sample_rate": 16000,
    "channels": 1
}
```

**Key behavior:**
- `interim_results` show real-time partial transcription in the UI (so the patient sees their words appearing)
- `is_final` transcripts are the only ones sent to LangGraph (to avoid processing incomplete sentences)
- `utterance_end_ms: 1000` means: after 1 second of silence, Deepgram considers the utterance complete

### TTS — Text-to-Speech

```python
# Convert LLM response to audio
tts_options = {
    "model": "aura-asteria-en",   # Natural female voice
    "encoding": "linear16",
    "sample_rate": 16000,
    "container": "none"           # Raw audio, no file wrapper
}

audio_bytes = await deepgram.speak.rest.v("1").stream(
    {"text": llm_response},
    options=tts_options
)
# Stream audio_bytes back to browser via WebSocket
```

---

## Component 4: LangGraph Agent (`src/agent_graph.py`)

### Purpose
The conversation brain. Implements the state machine that controls the call flow. Each node is a focused LLM call with access to specific tools.

### Graph Construction

```python
from langgraph.graph import StateGraph, START, END

def build_agent_graph():
    graph = StateGraph(CallState)

    # Add all nodes
    graph.add_node("emergency",      emergency_node)
    graph.add_node("auth",           auth_node)
    graph.add_node("new_patient",    new_patient_node)
    graph.add_node("routing",        routing_node)
    graph.add_node("faq",            faq_node)
    graph.add_node("scheduling",     scheduling_node)
    graph.add_node("cross_coverage", cross_coverage_node)
    graph.add_node("confirm",        confirmation_node)

    # Entry point
    graph.add_edge(START, "auth")

    # Conditional edges
    graph.add_conditional_edges("auth", route_after_auth,
        {"routing": "routing", "new_patient": "new_patient"})

    graph.add_edge("new_patient", "routing")

    graph.add_conditional_edges("routing", route_after_routing,
        {"scheduling": "scheduling", "faq": "faq", "routing": "routing"})

    graph.add_edge("faq", "routing")  # After answering FAQ, loop back

    graph.add_conditional_edges("scheduling", route_after_scheduling,
        {"confirm": "confirm", "cross_coverage": "cross_coverage"})

    graph.add_edge("cross_coverage", "confirm")
    graph.add_edge("confirm", END)
    graph.add_edge("emergency", END)

    return graph.compile()
```

### Per-Node LLM Prompt Strategy

Each node gets a **focused system prompt** so the LLM only handles one task at a time:

| Node | System Prompt Summary | Max Turns in Node |
|---|---|---|
| **AUTH** | "You are verifying the patient's identity. Ask for full name and date of birth. Nothing else." | 3 |
| **NEW_PATIENT** | "Collect: full name, DOB, phone, gender. Be warm and efficient." | 4 |
| **ROUTING** | "Ask the reason for their visit. Determine the medical specialty needed. You have access to the patient's medical history for context." | 3 |
| **FAQ** | "Answer the patient's question using ONLY the provided medical knowledge base results. Never diagnose." | 2 |
| **SCHEDULING** | "Present available time slots. Help the patient pick one. Confirm their choice." | 4 |
| **CROSS_COVERAGE** | "The patient's preferred doctor is unavailable. Offer an alternative doctor in the same department." | 3 |
| **CONFIRM** | "Read back: doctor name, date, time, location. Remind to bring ID, insurance card, medication bottles." | 1 |
| **EMERGENCY** | Fixed script — no LLM needed. Hardcoded 911 message. | 1 |

### Multi-Turn Handling Within a Node

Each node may require multiple conversational turns (e.g., AUTH asks for name, patient responds, AUTH asks for DOB, patient responds). The graph handles this by:

```
voice_server receives transcript
    │
    ▼
Is this a NEW utterance for the CURRENT node?
    │
    YES → append to state.full_history, re-invoke current node
    │     (node LLM sees the updated conversation, responds accordingly)
    │
    NO (node returned a "transition" signal) → move to next node via edge
```

Each node function returns either:
- `{"agent_response": "text", "transition": False}` → stay in this node, respond to patient
- `{"agent_response": "text", "transition": True}` → this node is done, follow the edge

---

## Component 5: EHR API (`src/ehr_server.py`)

### Purpose
A FastAPI REST API that wraps all Supabase queries. The LangGraph tools call these endpoints. It acts as the mock Epic EHR backend.

### Endpoint Details

#### `GET /api/patients/search`
**Used by:** AUTH node → `lookup_patient` tool

```python
# Request
GET /api/patients/search?first_name=John&last_name=Smith&dob=1985-03-12

# Logic
1. Query: patients WHERE first_name ILIKE '%John%' AND last_name ILIKE '%Smith%'
2. If DOB provided, add: AND dob = '1985-03-12'
3. If found, also fetch from medical_profiles WHERE patient_id = result.id
4. Return combined patient + clinical_data

# Response 200
{
  "found": true,
  "patient": {
    "id": "uuid", "mrn": "MRN-001", "first_name": "John",
    "last_name": "Smith", "dob": "1985-03-12", "phone": "555-123-4567"
  },
  "clinical_data": { ... }  // full JSONB from medical_profiles
}

# Response 404
{ "found": false, "message": "No patient found matching criteria" }
```

#### `POST /api/patients`
**Used by:** NEW_PATIENT node → `create_patient` tool

```python
# Request
POST /api/patients
{
  "first_name": "Jane",
  "last_name": "Doe",
  "dob": "1990-05-20",
  "phone": "555-999-0000",
  "gender": "female"
}

# Logic
1. Generate UUID for patient_id
2. Generate MRN (auto-increment or random)
3. INSERT into patients table
4. INSERT empty medical_profiles record (clinical_data = {})
5. Return new patient ID

# Response 201
{ "patient_id": "uuid", "mrn": "MRN-1042", "created": true }
```

#### `GET /api/providers`
**Used by:** ROUTING + SCHEDULING nodes → `search_providers` tool

```python
# By name
GET /api/providers?name=Peterson
# → SELECT * FROM doctors WHERE last_name ILIKE '%Peterson%'

# By specialty
GET /api/providers?specialty=Cardiology
# → SELECT * FROM doctors WHERE specialty = 'Cardiology' AND active = true

# Response 200
[
  {
    "id": "uuid", "first_name": "Elena", "last_name": "Rostova",
    "specialty": "Cardiology", "focus": "Interventional cardiology",
    "room": "Heart Institute Suite A", "extension": "Ext. 501",
    "booking_status": "PCP Referral required",
    "experience_years": 25
  }
]
```

#### `GET /api/providers/availability`
**Used by:** SCHEDULING + CROSS_COVERAGE nodes → `get_availability` tool

```python
# Request
GET /api/providers/availability?specialty=Family+Medicine&exclude_doctor=uuid

# Logic
1. Get all doctors in specialty (excluding specified doctor if cross-coverage)
2. For each doctor, check appointments table for open slots
3. Generate available slots based on clinic hours (Mon-Fri 7AM-7PM, 30-min slots)
4. Exclude already-booked slots
5. Return next 5 available slots per doctor

# Response 200
[
  {
    "doctor": { "id": "uuid", "name": "Dr. Sarah Jenkins", "room": "Room 102" },
    "available_slots": [
      "2026-05-05T10:00:00",
      "2026-05-05T14:00:00",
      "2026-05-06T09:00:00"
    ]
  }
]
```

#### `POST /api/appointments`
**Used by:** SCHEDULING node → `book_appointment` tool

```python
# Request
POST /api/appointments
{
  "patient_id": "uuid",
  "doctor_id": "uuid",
  "appointment_time": "2026-05-05T10:00:00",
  "reason": "Follow-up for chest discomfort"
}

# Logic
1. Verify slot is still available (no double-booking)
2. INSERT into appointments (status = "scheduled")
3. Return confirmation

# Response 201
{
  "appointment_id": "uuid",
  "status": "scheduled",
  "doctor_name": "Dr. Elena Rostova",
  "time": "2026-05-05T10:00:00",
  "room": "Heart Institute Suite A"
}
```

#### `POST /api/triage`
**Used by:** ROUTING + FAQ nodes → `search_rag` tool

```python
# Request
POST /api/triage
{ "question": "I've been having sharp chest pain for two days" }

# Logic
1. Generate embedding for the question
2. Query ChromaDB collection "healthcare_qa" (top 3 similar)
3. Return matched answers

# Response 200
{
  "results": [
    {
      "question": "What causes chest pain?",
      "answer": "Chest pain can be caused by...",
      "similarity_score": 0.89
    }
  ],
  "disclaimer": "This is general information only. For emergencies, call 911."
}
```

---

## Component 6: RAG Pipeline (`src/rag_pipeline.py`)

### Purpose
Ingests the `healthcare_qa.csv` into ChromaDB and provides a query interface for the triage endpoint.

### Architecture

```
rag_pipeline.py
│
├── ingest()                    ← Run once to populate ChromaDB
│   ├── Load healthcare_qa.csv
│   ├── For each row:
│   │   ├── Combine: question + answer → single document
│   │   ├── Metadata: { source: "healthcare_qa", question: "...", answer: "..." }
│   │   └── Auto-embed via ChromaDB's default embedding function
│   └── Persist to: ./data/chromadb/
│
├── query(question, top_k=3)   ← Called by /api/triage endpoint
│   ├── ChromaDB similarity search
│   └── Return top_k results with scores
│
└── ChromaDB Collection Config
    ├── Name: "healthcare_qa"
    ├── Embedding: sentence-transformers/all-MiniLM-L6-v2
    └── Distance metric: cosine
```

### Ingestion Script Usage

```bash
# One-time setup — run after downloading healthcare_qa.csv
python -m src.rag_pipeline --ingest

# Verify
python -m src.rag_pipeline --test "What causes headaches?"
```

---

## Component 7: LangGraph Tools (`src/tools/`)

### Purpose
Each tool is a Python function that the LangGraph nodes call to interact with the EHR API. Tools are thin wrappers — they format the request, call the API, and parse the response.

### Tool Registry

```python
# src/tools/patient_tools.py
def lookup_patient(first_name: str, last_name: str, dob: str) -> dict:
    """Search for an existing patient by name and date of birth."""
    response = requests.get(f"{EHR_URL}/api/patients/search",
        params={"first_name": first_name, "last_name": last_name, "dob": dob})
    return response.json()

def create_patient(first_name: str, last_name: str, dob: str,
                   phone: str, gender: str) -> dict:
    """Register a new patient in the system."""
    response = requests.post(f"{EHR_URL}/api/patients",
        json={"first_name": first_name, "last_name": last_name,
              "dob": dob, "phone": phone, "gender": gender})
    return response.json()

# src/tools/provider_tools.py
def search_providers(name: str = None, specialty: str = None) -> list:
    """Find doctors by name or specialty."""
    ...

def get_availability(specialty: str, exclude_doctor: str = None) -> list:
    """Get available appointment slots for a specialty."""
    ...

# src/tools/appointment_tools.py
def book_appointment(patient_id: str, doctor_id: str,
                     time: str, reason: str) -> dict:
    """Book a new appointment."""
    ...

def cancel_appointment(appointment_id: str) -> dict:
    """Cancel an existing appointment."""
    ...

# src/tools/triage_tools.py
def search_knowledge_base(question: str) -> dict:
    """Search the medical Q&A knowledge base for relevant answers."""
    ...
```

### Tool-to-Node Mapping

| Tool | Available In Node(s) | Why Restricted |
|---|---|---|
| `lookup_patient` | AUTH only | Can't look up patients before identifying them |
| `create_patient` | NEW_PATIENT only | Only during registration flow |
| `search_providers` | ROUTING, SCHEDULING | Need to find doctors |
| `get_availability` | SCHEDULING, CROSS_COVERAGE | Need available slots |
| `book_appointment` | SCHEDULING only | Only book after confirming slot |
| `cancel_appointment` | ROUTING only | When intent is "cancel" |
| `search_knowledge_base` | ROUTING, FAQ | Medical triage answers |

---

## Component 8: LLM Prompts (`src/prompts/`)

### Purpose
Each LangGraph node has a dedicated system prompt. Prompts are stored as separate files for easy editing without touching code.

### Example: AUTH Node Prompt

```python
# src/prompts/auth_prompt.py

AUTH_SYSTEM_PROMPT = """You are a friendly medical receptionist at Mercy General Hospital.

YOUR CURRENT TASK: Verify the patient's identity.

INSTRUCTIONS:
1. Greet the patient warmly.
2. Ask: "Could you please provide your full name?"
3. After receiving the name, ask: "And your date of birth?"
4. Once you have both, call the lookup_patient tool.
5. If the patient is found, say: "I found your record, [name]. Let me pull up your profile."
   Then signal TRANSITION to the next state.
6. If not found, say: "I don't see a record under that name. No worries — I can get you set up."
   Then signal TRANSITION to new_patient state.

RULES:
- Do NOT ask about symptoms, appointments, or insurance in this state.
- Do NOT provide medical advice.
- Keep responses short (2-3 sentences max) — this is a phone call.
- If the patient mentions an emergency, IMMEDIATELY signal EMERGENCY.

PATIENT'S CLINICAL HISTORY (if returning patient):
{clinical_data}
"""
```

### Example: EMERGENCY Node (No LLM — Hardcoded)

```python
# src/prompts/emergency_prompt.py

EMERGENCY_SCRIPT = (
    "I am an automated assistant and it sounds like you are experiencing "
    "a medical emergency. Please hang up and dial 911 immediately, or go "
    "to the nearest emergency room. I am disconnecting this call so you "
    "can seek emergency help."
)
# No LLM call — this text is sent directly to TTS
```

---

## Deployment Architecture (Cloud-Agnostic)

### Local Development

```
Terminal 1:  uvicorn src.voice_server:app --reload --port 8000
Terminal 2:  (browser opens frontend/index.html)
```

### Google Cloud (Cloud Run)

```
┌─────────────────────────────────────────────────────┐
│  Cloud Run Service                                   │
│  ├── Container: voice_server.py + ehr_server.py     │
│  ├── ChromaDB: persistent volume mount              │
│  └── WebSocket support: enabled                      │
│                                                      │
│  Environment Variables:                              │
│  ├── SUPABASE_URL, SUPABASE_KEY                     │
│  ├── DEEPGRAM_API_KEY                                │
│  └── OPENAI_API_KEY                                  │
└─────────────────────────────────────────────────────┘
         │                      │
         ▼                      ▼
   Supabase (external)    Deepgram (external)
```

### Docker Setup

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY src/ ./src/
COPY frontend/ ./frontend/
COPY data/chromadb/ ./data/chromadb/
EXPOSE 8000
CMD ["uvicorn", "src.voice_server:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Cross-Reference to Existing Docs

| This Component | Detailed In |
|---|---|
| Database schema (4 tables) | `docs/supabase_schema.md` |
| 25 Doctor roster | `docs/doctors.md` |
| Patient profile JSONB | `docs/patient_profile_template.md` |
| Scheduling & cross-coverage rules | `docs/scheduling_logic.md` |
| 6 core features | `docs/features.md` |
| Emergency + triage protocol | `clinic_knowledge_base.md` |
| Full project requirements | `PRD.md` |
| High-level architecture | `docs/system_architecture.md` |
