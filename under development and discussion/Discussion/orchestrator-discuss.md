# Orchestrator discussion

Working notes for **Component 03 — conversation orchestration**. We discuss and refine the orchestrator here before updating the canonical design docs.

## Related files

| File | Role |
|------|------|
| [system design/03-component-orchestration.md](../../system%20design/03-component-orchestration.md) | Canonical orchestrator design |
| [node-diagrams.md](./node-diagrams.md) | Outer graph + per-node tool diagrams |
| [tools.md](./tools.md) | Node list and per-node tool allowlists |
| [list of orchestrator components to plan.md](./list%20of%20orchestrator%20components%20to%20plan.md) | Nodes + tools checklist and plan status |
| [.agent/Plans/03_orchestrator_cards.md](../../.agent/Plans/03_orchestrator_cards.md) | Component 03 plan index |
| [.agent/Plans/03_orchestrator_01_session_start_emergency_gate.md](../../.agent/Plans/03_orchestrator_01_session_start_emergency_gate.md) | Sub-plan 01: `session_start` + `EMERGENCY_GATE` |
| [src/orchestrator/graph.py](../../src/orchestrator/graph.py) | Current implementation (minimal single `chat` node) |
| [progress.md](../../progress.md) | Component 03 status |

---

## Next up — per-node plans (prompt + tools)

**Agreed direction (2026-05-31):** Define a **plan for each outer node** before implementation. Each plan should cover at minimum:

| # | Plan item | Notes |
|---|-----------|--------|
| 1 | **Node prompt** | What the LLM must do / must not do in this step |
| 2 | **Tools** | Allowlist from [tools.md](./tools.md) §3 |
| 3 | **Enter** | When orchestrator moves *into* this node |
| 4 | **Exit** | When orchestrator moves *out* (completion rules) |
| 5 | **LLM?** | Yes / no (code-only nodes skip prompt) |

**Checklist — one plan per node:**

- [ ] `session_start` — see [Node plan: session_start & EMERGENCY_GATE](#node-plan-session_start--emergency_gate)
- [ ] `EMERGENCY_GATE` — see above
- [ ] `PLAY_911_SCRIPT`
- [ ] `PATIENT_IDENTIFY`
- [ ] `VERIFY_RETURNING`
- [ ] `REGISTER_SHELL_PROFILE`
- [ ] `CLINICAL_ROUTE`
- [ ] `RAG_ANSWER`
- [ ] `SCHEDULING`
- [ ] `CONFIRM_COMMIT`
- [ ] `INSURANCE_INTAKE`
- [ ] `HUMAN_HANDOFF`
- [ ] `wrap_up`

**Source of truth for tools:** [tools.md](./tools.md). **Flow:** [node-diagrams.md](./node-diagrams.md).

*(Per-node plan sections will be added below or in linked files as we work through them.)*

---

### Node plan: `session_start` & `EMERGENCY_GATE`

**Implementation plan:** [.agent/Plans/03_orchestrator_01_session_start_emergency_gate.md](../../.agent/Plans/03_orchestrator_01_session_start_emergency_gate.md) · Parent: [03_orchestrator_cards.md](../../.agent/Plans/03_orchestrator_cards.md)

#### `session_start` — what it does

**When:** Once, right after the call connects (WebRTC session created).

**Purpose:** Set up the call in memory — **no talking to the patient yet**, no LLM.

| Does | Does not |
|------|----------|
| Create / attach `session_id` | Ask medical questions |
| Load saved state if caller reconnects | Run the LLM |
| Set `active_node = PATIENT_IDENTIFY` (or first step after gate) | Call any tools |
| Initialize empty fields: `patient_id`, slots, etc. | Hear user speech yet (optional: play greeting — product choice) |

**Think of it as:** turning the computer on for this phone call — wiring is ready, conversation has not started.

**Today in code:** WebRTC `CallSession` creation in `server.py` is a **partial** version of this (session id + voice). Full `session_start` node in LangGraph is **not built yet**.

---

#### `EMERGENCY_GATE` — what it does

**When:** On **every** finalized user message — **before** any LLM node runs. Always first safety check.

**Purpose:** Catch **life-threatening** wording fast and **stop** normal scheduling flow.

| Does | Does not |
|------|----------|
| Scan user text for emergency keywords / patterns | Book appointments |
| If hit → go to `PLAY_911_SCRIPT` → end call | Have a conversation |
| If clear → allow normal flow (`PATIENT_IDENTIFY`, etc.) | Use LLM tools |
| Log `emergency_triggered` (reason class, not full PHI in logs per policy) | Replace keyword check with LLM-only judgment |

**PRD trigger examples:** chest pain, difficulty breathing, shortness of breath, sudden weakness, drooping face, severe bleeding, suicidal thoughts (+ synonyms in implementation).

**How it runs (design):**

```text
User text arrives
  → EMERGENCY_GATE (Python: keywords, maybe small classifier)
       ├─ HIT  → PLAY_911_SCRIPT → fixed 911 message → end_session
       └─ CLEAR → continue to active conversational node (LLM)
```

**911 script (PRD):** *"I am an automated assistant and it sounds like you are experiencing a medical emergency. Please hang up and dial 911 immediately."*

**Why no LLM here:** Must be **fast**, **deterministic**, and **cannot be talked around** by prompt injection or model error. LLM emergency hints in global prompt are **backup only** — gate is the real enforcement.

**Today in code:** Emergency words are only mentioned inside global `SYSTEM_PROMPT` — **no hard gate** before LLM yet.

---

#### What `EMERGENCY_GATE` contains (keyword work — not “meaning”)

You are right: this gate is **pattern / keyword matching**, not semantic understanding. You do **not** need a huge medical dictionary. You need a **small, curated, high-precision** list tuned for **life-threatening** cases only.

##### The gate is 4 parts (not just one word list)

| Part | What you build | Size / effort |
|------|----------------|---------------|
| **1. Core phrases** | PRD must-hit strings | ~6–12 **categories**, ~40–80 **phrases** total |
| **2. Synonyms & spoken variants** | How people actually say it on the phone | +30–50 phrases per category (ASR-friendly) |
| **3. Matcher code** | Normalize text → scan | One Python function (~50–150 lines) |
| **4. Audit + reason** | Log `reason_class` (e.g. `chest_pain`, `suicidal`) | Small enum, no transcript in logs if policy says so |

**You do not feed:** full ICD lists, every symptom, or RAG knowledge — that belongs in triage/RAG, not the gate.

##### PRD baseline (start here — your minimum set)

From [PRD.md](../../PRD.md) Feature 5 — one **category** each:

| Category (`reason_class`) | Example phrases to match |
|---------------------------|-------------------------|
| `cardiac` | chest pain, crushing chest, heart attack |
| `breathing` | can't breathe, difficulty breathing, shortness of breath, choking |
| `stroke_neuro` | sudden weakness, drooping face, face droop, slurred speech, stroke |
| `bleeding` | severe bleeding, bleeding heavily, won't stop bleeding |
| `suicidal` | suicidal, kill myself, want to die, end my life |
| `allergic_severe` | *(optional tier-2)* anaphylaxis, throat closing, can't swallow |

Add **synonyms** per row — not new categories unless PRD/product adds them.

##### Example expanded list (illustrative — not exhaustive)

```text
cardiac:
  chest pain, chest hurts, pain in my chest, tightness in chest,
  heart attack, having a heart attack

breathing:
  can't breathe, cannot breathe, trouble breathing, hard to breathe,
  shortness of breath, short of breath, gasping, choking

stroke_neuro:
  face drooping, drooping face, face is numb, sudden weakness,
  weak on one side, slurred speech, think i'm having a stroke

bleeding:
  severe bleeding, bleeding a lot, won't stop bleeding,
  bleeding heavily, losing a lot of blood

suicidal:
  suicidal, suicide, kill myself, hurt myself, want to die,
  end my life, don't want to live
```

**Rough total:** ~50–120 strings after expansion — manageable in one config file (YAML/JSON/Python set).

##### Matcher rules (how keywords work in code)

```text
1. lowercase
2. strip extra whitespace
3. optional: remove filler ("um", "like") — careful, don't break phrases
4. match modes:
   - phrase in text  ("chest pain" in utterance)  ← primary
   - word boundary for short words  ("stroke", "911")  ← avoid false hits
5. optional: whole-word denylist for false positives (see below)
```

**Do not** require exact full-sentence match — STT rarely gives perfect sentences.

##### ASR / voice extras (worth adding)

| Trick | Why |
|-------|-----|
| **Numeric 911** | user says "nine one one" or "911" |
| **Common mis-hearings** | maintain from real call logs later |
| **Partial phrases** | "can't breath" (missing e) if you see STT pattern |

Start with clean phrases; **expand from logged misses** after testing — not upfront guessing.

##### False positives (keyword downside)

Keyword match ≠ meaning, so you **will** get some false hits:

| Utterance | Risk |
|-----------|------|
| "I had chest pain **last year**, need a follow-up" | May trigger cardiac |
| "My **child** has chest pain" | Still may be real emergency — product may want trigger anyway |

**Policy choices:**

- **High sensitivity (safer):** trigger on keyword even in past tense → more 911 scripts, fewer misses  
- **Medium:** add simple excludes (`last year`, `years ago`, `history of`) — more code, still not perfect  
- **Never** try to solve all nuance with keywords alone — that's why optional classifier exists in design doc

For v1, PRD says **zero tolerance** → **bias toward trigger** when category phrase matches.

##### What NOT to put in the gate

| Skip | Put instead in |
|------|----------------|
| "headache", "fever", "stomach ache" (non-severe) | `CLINICAL_ROUTE` / RAG routing |
| "book ER appointment" | scheduling flow |
| Full symptom triage | `retrieve_kb` / department policies |
| Thousands of medical terms | unnecessary latency + false alarms |

##### How much work for you

| Task | Estimate |
|------|----------|
| First pass list from PRD + synonyms | **2–4 hours** |
| Matcher function + unit tests | **2–4 hours** |
| Tune from 20–50 test utterances | **ongoing** |
| LLM classifier (optional later) | separate; not required for v1 |

**Deliverable file (suggested):** `src/orchestrator/emergency_keywords.py` or `config/emergency_phrases.yaml` with `CATEGORIES` dict.

##### Test cases you should write (examples)

```text
MUST trigger:
  "I have chest pain right now"
  "I can't breathe"
  "I'm having thoughts of suicide"

MUST NOT trigger (v1 if you add excludes):
  "I need to schedule a checkup"
  "What are your parking hours?"

EDGE (product decision):
  "I had chest pain yesterday, need an appointment"
```

##### One line

> **Emergency gate = small curated phrase list (~50–120 lines) + simple matcher + reason code — not medical NLP, not LLM meaning.**

---

##### Hybrid idea: keywords in gate + LLM backup in node prompts

**Proposal:** `EMERGENCY_GATE` = keywords only. First LLM node after (`PATIENT_IDENTIFY`) has an enhanced prompt: if the model "catches" emergency wording, shift straight to the 911 script.

**Verdict:** **Good as a second layer — not a replacement for the keyword gate.**

| Layer | Role |
|-------|------|
| **1. `EMERGENCY_GATE` (keywords)** | Every message, **before** LLM — fast, mandatory |
| **2. LLM nodes (all of them, not only first)** | Backup — catch phrasing keywords missed ("I can't catch my breath") |

**Do not put backup only on `PATIENT_IDENTIFY`.** Emergency can appear in `SCHEDULING`, `CLINICAL_ROUTE`, etc. Every **LLM node prompt** should include the same escalation rule (or global prompt already does — node prompt repeats it).

**Critical: LLM must not "just say call 911" and keep chatting.**

The model must **signal the orchestrator** to change graph state:

```text
Option A — structured tool (recommended):
  LLM calls trigger_emergency(reason="breathing")  → orchestrator-only tool
  → skip normal reply → PLAY_911_SCRIPT → end_session

Option B — structured output flag:
  LLM returns { "emergency": true, "reason_class": "breathing" }
  → orchestrator reads flag before TTS → script path

Option C — bad:
  LLM only says "please call 911" in AIMessage but graph stays in SCHEDULING
```

**Latency:** No extra LLM call — backup runs **inside the turn you already pay for** when a conversational node runs. Keyword gate still adds ~0 ms; LLM backup adds **zero** if merged into same invoke.

**Flow:**

```text
User text
  → EMERGENCY_GATE (keywords) ──HIT──► PLAY_911_SCRIPT
  → CLEAR
  → PATIENT_IDENTIFY (LLM + node prompt + tools)
       → LLM sees new emergency phrasing
       → trigger_emergency OR emergency flag
       → orchestrator → PLAY_911_SCRIPT (same path as keywords)
       → else normal reply
```

**Prompt snippet (every LLM node):**

```text
If the caller describes a possible medical emergency (chest pain, can't breathe,
severe bleeding, stroke signs, suicidal intent, etc.) — even if phrased unusually —
do NOT schedule or triage. Call trigger_emergency immediately. Do not continue
the conversation.
```

**Tradeoffs:**

| Pros | Cons |
|------|------|
| Catches paraphrases keywords miss | Slower than keywords; can miss or hesitate |
| No second API round-trip | Must wire orchestrator handoff — not prompt-only |
| Defense in depth | False positive possible — same policy as keywords |

**v1 recommendation:** Ship **keyword gate** + **`trigger_emergency` tool** on all LLM nodes. Optional small classifier later if logs show gaps.

---

#### How they work together at call start

```text
1. session_start     → session ready, active_node set
2. (user speaks)
3. EMERGENCY_GATE    → every message, first
4. PATIENT_IDENTIFY  → first LLM step if gate clears
```

---

## Discussion log

### 2026-05-31 — Next: plan each node with tools

**Direction:** Build a plan per outer node (node prompt, tools, enter/exit rules). Tracked in [Next up — per-node plans](#next-up--per-node-plans-prompt--tools).

---

### 2026-05-31 — Session start

**Status:** Beginning discussion and understanding of the orchestrator before implementation.

### 2026-05-31 — LLM nodes without node prompt? What is `chat`?

**Question:** Any node gets global + text + history without its own prompt? What is chat node?

**Answer:** Full design = every LLM node has node prompt. `chat` is today's stub (global only). See [Q: Any LLM node with no node prompt](#q-any-llm-node-with-global--text--history-but-no-node-prompt-what-is-chat).

---

### 2026-05-31 — Only active node LLM gets prompts + history?

**Question:** Global + text + history goes to active node LLM only (e.g. PATIENT_IDENTIFY)?

**Answer:** Yes. Confirmed in [Q: Only the active node's LLM](#q-only-the-active-nodes-llm-gets-global--node-prompt--text--history).

---

### 2026-05-31 — Inside LangGraph: global + text + history per node

**Question:** How does LangGraph handle global + my text + history based on our nodes?

**Answer:** State holds history + active_node; each graph node function rebuilds global + node prompt, runs LLM + tools. See [Q: Inside LangGraph](#q-inside-langgraph--how-is-global--my-text--history-handled-per-node).

---

### 2026-05-31 — handle_transcript vs LangGraph — who has the LLM?

**Question:** handle_transcript builds messages (no LLM?), LangGraph gets global + text + history, then what?

**Answer:** Yes — prep in handle_transcript, LLM only in LangGraph. See [Q: handle_transcript has no LLM](#q-handle_transcript-has-no-llm--langgraph-gets-messages-then-what).

---

### 2026-05-31 — Text "Hello" already exists — who gets it? (no voice pipeline)

**Question:** Skip voice — text `"Hello"` is already inside the system. Who receives it?

**Answer:** **`handle_transcript`** in `src/orchestrator/__init__.py`. That is the single entry point for text today.

#### Starting from text only

```text
Input:  { session_id: "abc", text: "Hello" }
          ↓
handle_transcript(event)          ← YOU ARE HERE (orchestrator entry)
          ↓
(today) append to messages, call LangGraph
(future) emergency gate → active node → prompts + tools → LangGraph
          ↓
Output: reply string  "Hi, welcome to Mercy General..."
```

**LangGraph does not receive raw text directly from the outside.**  
`handle_transcript` receives it, prepares state, **then** calls LangGraph.

#### What `handle_transcript` does today (line by line)

```python
# src/orchestrator/__init__.py

text = "Hello"

# 1. First message this session? → create message list with global prompt
if session_id not in _sessions:
    _sessions[session_id] = [SystemMessage(SYSTEM_PROMPT)]

# 2. Add user text to conversation
_sessions[session_id].append(HumanMessage("Hello"))

# 3. Pass full message list to LangGraph
result = await graph.ainvoke({"messages": _sessions[session_id]})

# 4. Save updated history, return LLM reply text
return "Hi, how can I help you today?"
```

#### What LangGraph receives (not raw "Hello" alone)

LangGraph gets a **state object**:

```text
{
  "messages": [
    SystemMessage("You are Mercy General voice receptionist..."),   ← global prompt
    HumanMessage("Hello")                                          ← your text
  ]
}
```

The **`chat` node** inside the graph sends that to the LLM → gets `AIMessage` back.

#### Full design (future) — same entry, more logic before LangGraph

```text
handle_transcript("Hello")

  1. Load session state (active_node, patient_id, etc.)

  2. EMERGENCY_GATE on "Hello" → pass

  3. active_node = PATIENT_IDENTIFY

  4. Build messages:
       global prompt
     + node prompt ("collect name, DOB...")
     + history (if any)
     + HumanMessage("Hello")
     + bind tools: [lookup_patient]

  5. LangGraph invoke (current node function runs LLM)

  6. Maybe tool calls → run tools → LLM again

  7. Return reply string to whoever called handle_transcript
```

Still **one front door:** `handle_transcript`. Nodes are **inside** that function / LangGraph — not separate receivers of text.

#### Simple picture (text-only)

```
                    ORCHESTRATOR
                    ┌─────────────────────────────────┐
  "Hello" ────────► │  handle_transcript            │
                    │    • session state              │
                    │    • emergency gate (future)    │
                    │    • which node (future)        │
                    │    • build messages + tools     │
                    │         │                       │
                    │         ▼                       │
                    │    LangGraph (LLM)              │
                    │         │                       │
                    │         ▼                       │
  "Hi, welcome..." ◄│    return reply                 │
                    └─────────────────────────────────┘
```

#### One line

> Text enters at **`handle_transcript`** → orchestrator prepares everything → **LangGraph/LLM** → reply string out.

---

### Q: `handle_transcript` has no LLM — LangGraph gets messages, then what?

**Short answer:** **Correct.** `handle_transcript` = **prep only** (no LLM). **LangGraph** = where the **LLM actually runs**.

#### Split of jobs

| Part | Has LLM? | What it does |
|------|----------|--------------|
| **`handle_transcript`** | **No** | Receives `"Hello"`, loads session, builds message list, calls LangGraph, returns reply text |
| **LangGraph `chat` node** | **Yes** | Receives message list → `llm.invoke(messages)` → adds AI reply to list |

#### Step by step after you said "Hello"

```text
STEP 1 — handle_transcript (NO LLM)
────────────────────────────────────
  messages = [
    SystemMessage(global prompt),
    HumanMessage("Hello")
  ]

STEP 2 — call LangGraph
────────────────────────────────────
  graph.ainvoke({ "messages": messages })

STEP 3 — inside LangGraph, chat node (LLM RUNS HERE)
────────────────────────────────────
  response = llm.invoke(state["messages"])    ← OpenAI API call
  return messages + [AIMessage("Hi, welcome to Mercy General...")]

STEP 4 — back in handle_transcript (NO LLM)
────────────────────────────────────
  save updated messages to _sessions
  return last message text to caller
```

#### What LangGraph receives vs what it returns

**Receives (input state):**
```text
{
  "messages": [
    SystemMessage("You are Mercy General..."),   ← global
    HumanMessage("Hello")                        ← your text
    ... older HumanMessage / AIMessage ...       ← history (turn 2+)
  ]
}
```

**Returns (output state):**
```text
{
  "messages": [
    SystemMessage(...),
    HumanMessage("Hello"),
    AIMessage("Hi, welcome to Mercy General. How can I help?")   ← NEW
  ]
}
```

`handle_transcript` peels off that last `AIMessage` and returns the string.

#### Code proof

`handle_transcript` — no LLM, only list building + invoke:

```28:34:src/orchestrator/__init__.py
    if session_id not in _sessions:
        _sessions[session_id] = [SystemMessage(content=SYSTEM_PROMPT)]

    _sessions[session_id].append(HumanMessage(content=text))

    try:
        result = await _get_graph().ainvoke({"messages": _sessions[session_id]})
```

LLM only inside LangGraph `chat` node:

```30:32:src/orchestrator/graph.py
    def chat(state: OrchestratorState) -> OrchestratorState:
        response = llm.invoke(state["messages"])
        return {"messages": state["messages"] + [response]}
```

#### Future full design — same split

| Layer | LLM? |
|-------|------|
| `handle_transcript` | No — emergency gate, active node, attach node prompt + tools |
| LangGraph node function (e.g. `patient_identify`) | **Yes** — `llm.invoke` with tools |

Prep stays outside (or in graph routing code). **Talking to the model** stays inside LangGraph nodes.

#### One line

> **`handle_transcript` = secretary (assemble the file). LangGraph = doctor (read file and write answer).**

---

### Q: Inside LangGraph — how is global + my text + history handled per node?

**Short answer:** LangGraph holds **state** (messages + active node + session facts). On each turn it **routes to one graph node function**. That function **builds what the LLM sees** (global + node prompt + history + new text), runs the LLM (+ tools), appends the reply to history.

---

#### TODAY (code now) — one node, simple

State is **only** `messages`:

```text
messages = [
  SystemMessage(global prompt),     ← always first
  HumanMessage("Hello"),            ← turn 1
  AIMessage("Hi, how can I help?"), ← turn 1 reply
  HumanMessage("I need a doctor"),  ← turn 2 (history)
]
```

LangGraph has **one** node `chat`. It sends **the entire list** to the LLM. No routing, no node prompt, no tools.

```text
START → chat (llm.invoke(all messages)) → END
```

---

#### FULL DESIGN — how it works with our 13 outer nodes

LangGraph state grows:

```text
{
  "messages":        [ ... conversation history ... ],
  "active_node":     "PATIENT_IDENTIFY",    ← which outer step
  "patient_id":      null,
  "proposed_slot":   null,
  ...
}
```

**Important:** `messages` stores **the conversation** (user + assistant turns, and optionally tool results).  
**Global + node prompts** are usually **re-built each turn** — not duplicated forever in history (keeps tokens clean).

##### What the LLM actually sees on one turn (example: turn 3, node = PATIENT_IDENTIFY)

```text
┌─ built fresh this turn ─────────────────────────────┐
│ SystemMessage(GLOBAL_PROMPT)                        │
│ SystemMessage(NODE_PROMPT_IDENTIFY)                 │
│   "Collect name, DOB, returning vs new..."          │
├─ from history (saved in state.messages) ────────────┤
│ HumanMessage("Hello")                               │
│ AIMessage("Hi, welcome to Mercy General...")        │
│ HumanMessage("I'm John Smith, DOB March 5 1980")    │  ← new text this turn
└─────────────────────────────────────────────────────┘
        +
  tools bound for this node: [lookup_patient]
        ↓
      llm.invoke(...)
```

| Piece | Stored in history forever? | Changes when node changes? |
|-------|---------------------------|----------------------------|
| Global prompt | Re-injected each turn (or once at start) | No |
| Node prompt | Re-injected each turn | **Yes** — different text per node |
| User / AI messages | **Yes** — grows every turn | No (same history across nodes) |
| Tool results | **Yes** — appended when tools run | Tools available change per node |

**History crosses nodes.** When you move from `PATIENT_IDENTIFY` → `SCHEDULING`, the LLM still sees prior "Hello" / name / DOB exchange — only the **node prompt + tools** swap.

---

##### LangGraph shape (target architecture)

```text
                    ┌─────────────────┐
START ─────────────►│ emergency_gate  │  (code only, no LLM)
                    └────────┬────────┘
                             │ cleared
                    ┌────────▼────────┐
                    │ route_by_node   │  reads state.active_node
                    └────────┬────────┘
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
  patient_identify      scheduling         confirm_commit
  (LLM + lookup)        (LLM + calendar)   (LLM + book)
         │                   │                   │
         └───────────────────┴───────────────────┘
                             │
                    check: node complete?
                             │
                    update active_node OR stay
                             │
                            END   (wait for next user message)
```

**One user message = one graph run** (today's pattern). Graph runs the **current** node, returns reply, exits. Next user message triggers another run.

Nodes **without LLM** (`EMERGENCY_GATE`, `PLAY_911_SCRIPT`, `wrap_up`) are graph nodes that run **Python only** — they never call `llm.invoke`.

---

##### Inner loop inside one LangGraph node (e.g. SCHEDULING)

Same turn can spin **multiple LLM calls** if tools are used:

```text
1. LLM sees: global + node prompt + history + user text
2. LLM returns: tool_call get_availability(...)
3. Orchestrator runs tool → ToolMessage(result)
4. LLM called again with history + tool result
5. LLM returns: AIMessage("I have Tuesday 2pm...")
6. That AIMessage saved to state.messages
```

User hears one reply; internally maybe 2+ LLM calls.

---

##### Example across nodes (3 user messages)

| Turn | active_node | Node prompt says | Tools | User says |
|------|-------------|------------------|-------|-----------|
| 1 | `PATIENT_IDENTIFY` | collect identity | `lookup_patient` | "Hello, I'm John" |
| 2 | `PATIENT_IDENTIFY` | same | same | "DOB March 5 1980" |
| 3 | `VERIFY_RETURNING` | verify + load profile | `lookup_patient`, `get_patient_profile` | "Yes that's correct" |

Turn 1–2: **same node** → same node prompt + tools; history grows.  
After turn 2: orchestrator sets `active_node = VERIFY_RETURNING`.  
Turn 3: **new node prompt + tools**, but history still has Hello / John / DOB.

---

##### Summary table — who handles what inside LangGraph

| Job | Where in LangGraph |
|-----|-------------------|
| Store chat history | `state.messages` |
| Remember which outer step | `state.active_node` |
| Pick graph node function | `route_by_node` (conditional edge) |
| Attach global + node prompt | Inside each LLM node function (each turn) |
| Attach tools | Inside each LLM node function (allowlist per node) |
| Run LLM | Inside each LLM node function |
| Move to next outer node | After node function — orchestrator checks rules, updates `active_node` |

---

#### One line

> **History = one shared story. Node = which instructions + tools get layered on top each turn. LangGraph routes to the right node function to do that.**

---

### Q: Only the active node's LLM gets global + node prompt + text + history?

**Short answer:** **Yes — exactly right.**

When `active_node = PATIENT_IDENTIFY`, **only** the `patient_identify` graph function runs the LLM. Other nodes (`SCHEDULING`, `CONFIRM_COMMIT`, …) **do not run** that turn.

#### What gets passed to the LLM (one active node only)

```text
active_node = PATIENT_IDENTIFY

patient_identify node function runs:
  LLM input =
    global prompt
  + node prompt ("collect name, DOB, returning vs new...")
  + history (prior user + assistant messages)
  + my text (this turn)
  + tools: [lookup_patient]

SCHEDULING node     → not called
CONFIRM_COMMIT node → not called
```

#### One LLM model, one active node function

| Correct | Wrong |
|---------|-------|
| One LLM, **one node function runs per turn** | Every node runs LLM every turn |
| Only **active** node sees the messages | All nodes get global + text + history at once |
| Other nodes **wait** until orchestrator switches `active_node` | Separate LLM brain per node |

Same `ChatOpenAI` instance in code — but **only the current node's function** calls `llm.invoke` that turn.

#### Nodes without LLM (never get this package)

These run **code/script only** — no `global + node prompt + history` to LLM:

- `session_start`
- `EMERGENCY_GATE`
- `PLAY_911_SCRIPT`
- `wrap_up`

#### When node changes

```text
Turn N:   active_node = PATIENT_IDENTIFY
          → patient_identify LLM gets global + IDENTIFY node prompt + history + text

Turn N+1: orchestrator moves active_node = VERIFY_RETURNING
          → verify_returning LLM gets global + VERIFY node prompt + history + text
          → PATIENT_IDENTIFY function NOT called
```

History is **shared**. Node prompt + tools **switch** with `active_node`.

#### Your sentence — confirmed

> If the system is on `PATIENT_IDENTIFY`, **only that node's function** calls the LLM with **global prompt + node prompt + my text + history** (+ tools for that node). Other nodes do not run.

**Today in code:** only one node exists (`chat`), so routing is trivial — but same idea: one node function, one LLM call per user message.

---

### Q: Any LLM node with global + text + history but NO node prompt? What is `chat`?

**Short answer:** In the **full design**, every node that uses the LLM gets **global + node prompt + history + text**. The **`chat` node** is **not** part of the 13-node design — it is **today's temporary stub** in code with **only global prompt** (no node prompt).

#### Two different things — don't mix them up

| Name | What it is |
|------|------------|
| **`chat` node** | **Current code only** (`graph.py`). One catch-all step. **Not** in `tools.md` / `node-diagrams.md`. |
| **`PATIENT_IDENTIFY`, `SCHEDULING`, …** | **Full design** — the 13 outer nodes we documented. |

`chat` will be **replaced** by the real node functions when you implement Component 03.

#### What `chat` sends to the LLM today

```text
chat node (stub — no node prompt):

  SystemMessage(global prompt ONLY)
  + history
  + HumanMessage(your text)

  → llm.invoke()
```

No `PATIENT_IDENTIFY` prompt. No tools. Global prompt tries to cover everything — that's why it's incomplete vs the design.

#### Full design — LLM nodes: all get a node prompt

Every outer node that **talks via LLM** gets **global + node prompt + history + text + tools**:

| Node | LLM? | Node prompt? |
|------|------|--------------|
| `PATIENT_IDENTIFY` | Yes | Yes — "collect identity…" |
| `VERIFY_RETURNING` | Yes | Yes — "verify and load profile…" |
| `REGISTER_SHELL_PROFILE` | Yes | Yes — "register new patient…" |
| `CLINICAL_ROUTE` | Yes | Yes — "reason for visit, routing…" |
| `RAG_ANSWER` | Yes | Yes — "answer from KB only, no diagnosis…" |
| `SCHEDULING` | Yes | Yes — "find slots, do NOT book…" |
| `CONFIRM_COMMIT` | Yes | Yes — "read back summary, confirm before book…" |
| `INSURANCE_INTAKE` | Yes | Yes — "collect insurance…" |
| `HUMAN_HANDOFF` | Maybe | Yes if LLM speaks — "explain handoff…" |

**No design node** is meant to run LLM with global-only and skip the node prompt.

#### Nodes that never send anything to the LLM

These **do not receive** global + text + history at all — **no LLM, no prompts**:

| Node | What runs instead |
|------|-------------------|
| `session_start` | Python: create session, set `active_node` |
| `EMERGENCY_GATE` | Python: keyword check |
| `PLAY_911_SCRIPT` | Fixed script text → TTS |
| `wrap_up` | Fixed goodbye / summary (template or short LLM — product choice) |

#### Visual — three categories

```text
CATEGORY A — No LLM (code/script only)
  session_start, EMERGENCY_GATE, PLAY_911_SCRIPT, wrap_up*

CATEGORY B — LLM + global + NODE prompt (full design — all conversational steps)
  PATIENT_IDENTIFY, VERIFY_RETURNING, REGISTER_SHELL_PROFILE,
  CLINICAL_ROUTE, RAG_ANSWER, SCHEDULING, CONFIRM_COMMIT,
  INSURANCE_INTAKE, HUMAN_HANDOFF*

CATEGORY C — TODAY ONLY — stub `chat` node
  LLM + global prompt only (no node prompt, no routing, no tools)
  ← this is what confuses people; it's not the final design
```

*`wrap_up` / `HUMAN_HANDOFF` may use template or LLM — if LLM, still use a node prompt.

#### Why `chat` exists

Before building the full graph, the project wired **one** LangGraph node so voice → STT → LLM → TTS works end-to-end. It is a **placeholder**, not a 14th design node.

```python
# graph.py today — will become many nodes later
builder.add_node("chat", chat)   # ← temporary name, not PATIENT_IDENTIFY
```

#### One line

> **`chat` = today's shortcut (global only). Real design = every LLM node gets global + its own node prompt. No-LLM nodes get nothing sent to the model.**

---

### 2026-05-31 — "Hello" → text → who receives it? (with voice pipeline)

**Question:** STT converts "Hello" to text — does LangGraph receive it first?

**Answer:** No — Gateway → `handle_transcript` → then LangGraph. See [Q: User says Hello](#q-user-says-hello--text--who-receives-it-langgraph).

---

### 2026-05-31 — How does system start and move?

**Question:** Before session start, does global prompt + LLM run? How does start → move work?

**Answer:** Connect first (no LLM). Global prompt loads on first LLM need. Orchestrator sets first node — LLM doesn't pick. See [Q: How does the system start and move](#q-how-does-the-system-start-and-move-before-session-global-prompt-first-node).

---

### 2026-05-31 — Global agent picks the node?

**Question:** Graph starts with global prompt, that decides which node, node communicates, then next node?

**Answer:** Almost — orchestrator (code) picks nodes, not the global prompt/LLM. See [Q: Graph starts with global agent](#q-graph-starts-with-global-agent-it-picks-the-node-node-talks-then-next-node).

---

### 2026-05-31 — Prompt + tools change each communication step?

**Question:** We change prompt and tools with each step of communication, right?

**Answer:** Only when the **outer node** changes — not every message. See [Q: Do prompt and tools change](#q-do-prompt-and-tools-change-with-each-step-of-communication).

---

### 2026-05-31 — Are nodes separate agents?

**Question:** Don't all nodes become separate agents?

**Answer:** No — one agent, many workflow steps. See [Q: Are nodes separate agents?](#q-are-nodes-separate-agents).

---

### 2026-05-31 — System prompt + nodes + LLM + tools?

**Question:** Global system prompt on top, then nodes, and each node has LLM with tools?

**Answer:** Yes. See [Q: System prompt on top](#q-system-prompt-on-top-then-nodes-then-llm--tools-inside-each-node).

---

### 2026-05-31 — Tools list by node

**Answer:** 14 LLM tools total, mapped per node in [All tools by node](#all-tools-by-node--14-llm-tools-from-toolsmd-2–3).

---

### 2026-05-31 — How many nodes start to end?

**Answer:** 13 outer nodes total. Happy path is 9 steps (with one branch at step 4). Listed in [All outer nodes](#all-outer-nodes--13-total-from-toolsmd-1).

---

### 2026-05-31 — Plain English recap (outer = where on map, inner = what happens there)

**Question:** So outer = which node I'm in vs others, and inner = what happens on that node?

**Answer:** Yes. See [READ THIS FIRST](#read-this-first--outer-vs-inner-in-plain-english).

---

### 2026-05-31 — Outer vs inner (from tools.md)

**Question:** What is “outer graph” and what is “inner”?

### 2026-05-31 — Does the node have the LLM, or only tools?

**Question:** Every node is outer and tools are inner — but does the **node** have the LLM to communicate, or only the tools?

**Answer:** Documented in [Notes → Q: Where does the LLM live?](#q-where-does-the-llm-live-node-vs-tools).

---

**Current code:** `src/orchestrator/graph.py` is a stub — one `chat` node, no emergency gate, no tools, no state machine.

**Open topics** *(add questions and notes below as we go)*

- [ ] Outer graph: node transitions and when the orchestrator advances vs stays in place
- [ ] Emergency gate: keyword layer vs optional classifier; runs on every final transcript
- [ ] Inner loop: how LLM + tool calls work inside a node (e.g. `SCHEDULING`)
- [ ] Tool allowlists per node — align with [tools.md](./tools.md)
- [ ] RAG spoke (`RAG_ANSWER`) — when to enter/exit; return to `CLINICAL_ROUTE`
- [ ] Human handoff triggers
- [ ] LangGraph mapping: nodes, edges, state shape, checkpointing

---

## Notes

### READ THIS FIRST — outer vs inner in plain English

You got it. Here it is with zero jargon.

---

#### Two questions the system always answers

| Question | Layer | Answer looks like |
|----------|-------|-------------------|
| **“Where am I in the call, compared to all other steps?”** | **OUTER graph** | “We are in `SCHEDULING`. Identity is done. Booking is not done yet.” |
| **“What happens right now while we sit in this step?”** | **INNER (inside that node)** | “The LLM talks to the user. Maybe it calls `get_availability`. User picks a time. We stay in `SCHEDULING` until rules say move on.” |

**Outer** = position on the **roadmap** (one of many nodes).  
**Inner** = **activity inside that one stop** on the roadmap (LLM + tools).

---

#### One picture

```
WHOLE CALL (outer graph — you can only be in ONE box at a time)

  [IDENTIFY] → [VERIFY] → [ROUTE] → [SCHEDULING] → [CONFIRM] → [DONE]
                                         ↑
                                    YOU ARE HERE
                                         │
                    ┌────────────────────┴────────────────────┐
                    │  INSIDE this box (inner)                │
                    │  • LLM chats with patient               │
                    │  • LLM may call tools (calendar, etc.)  │
                    │  • repeat until step is complete        │
                    └─────────────────────────────────────────┘
```

You do **not** jump from `IDENTIFY` to `CONFIRM` because the LLM felt like it. The **outer** graph only advances when that step’s job is done (rules / orchestrator code).

While you **stay** in `SCHEDULING`, the **inner** loop can spin many times: ask question → call tool → speak → ask again → call tool again. Same outer box. Different inner turns.

---

#### What lives where (one table)

| Thing | Outer or inner? |
|-------|-----------------|
| Node names: `PATIENT_IDENTIFY`, `SCHEDULING`, `CONFIRM_COMMIT`, … | **Outer** — where you are on the map |
| “Move to next node when user verified” | **Outer** — orchestrator rules |
| LLM speaking to the patient | **Inner** — happens **inside** the current node |
| Tools: `lookup_patient`, `get_availability`, `book_appointment` | **Inner** — but **which** tools exist depends on **which outer node** you’re in |
| Emergency keyword check before anything else | **Outer** — runs on every message, before inner work |

---

#### Same LLM, different node = different inner setup

It is **one LLM** (same model). What changes when the **outer** node changes:

1. **System prompt** — “You are identifying the patient” vs “You are finding appointment slots”
2. **Tool menu** — in `SCHEDULING` you get calendar tools; in `CONFIRM_COMMIT` you get `book_appointment`
3. **When you’re allowed to leave** — orchestrator decides outer transition, not the LLM

Tools never talk to the user. **Only the LLM talks.** Tools are just data buttons the LLM presses while inside a node.

---

#### 10-second version

> **Outer graph** = *which step of the reception desk workflow we’re on.*  
> **Inner** = *the receptionist (LLM) working that step, optionally hitting backend tools.*

That’s the whole design.

---


**Short answer:** **Outer** = which **stage** of the call you are in (the boss’s checklist). **Inner** = what the **LLM can do** while stuck in that one stage (the worker’s allowed actions).

They are two layers. The LLM never runs the whole call by itself.

---

#### Outer graph = the call flow (orchestrator FSM)

### All outer nodes — **13 total**

**Happy path (start → end):**

1. `session_start`
2. `EMERGENCY_GATE`
3. `PATIENT_IDENTIFY`
4. `VERIFY_RETURNING` or `REGISTER_SHELL_PROFILE`
5. `CLINICAL_ROUTE`
6. `SCHEDULING`
7. `CONFIRM_COMMIT`
8. `INSURANCE_INTAKE`
9. `wrap_up`

**Side paths:** `RAG_ANSWER` (FAQ spoke), `PLAY_911_SCRIPT` (emergency), `HUMAN_HANDOFF` (fallback)

**All 13:** `session_start`, `EMERGENCY_GATE`, `PLAY_911_SCRIPT`, `PATIENT_IDENTIFY`, `VERIFY_RETURNING`, `REGISTER_SHELL_PROFILE`, `CLINICAL_ROUTE`, `RAG_ANSWER`, `SCHEDULING`, `CONFIRM_COMMIT`, `INSURANCE_INTAKE`, `HUMAN_HANDOFF`, `wrap_up`

### All tools by node — **14 LLM tools** (from [tools.md](./tools.md) §2–3)

**Grand total in catalog:** 14 tools the LLM can call (+ `end_session` is orchestrator/gateway direct, not in node allowlists).

| Node | Tools allowed | Count |
|------|---------------|-------|
| `session_start` | *(none — bootstrap only)* | 0 |
| `EMERGENCY_GATE` | *(none — keyword/classifier only)* | 0 |
| `PLAY_911_SCRIPT` | *(none — fixed script)* | 0 |
| `PATIENT_IDENTIFY` | `lookup_patient` | 1 |
| `VERIFY_RETURNING` | `lookup_patient`, `get_patient_profile` | 2 |
| `REGISTER_SHELL_PROFILE` | `create_shell_patient` | 1 |
| `CLINICAL_ROUTE` | `get_department_policies`, `note_chief_complaint` | 2 |
| `RAG_ANSWER` | `retrieve_kb` | 1 |
| `SCHEDULING` | `search_providers`, `get_availability` | 2 |
| `CONFIRM_COMMIT` | `book_appointment`, `reschedule_appointment`, `cancel_appointment`, `update_appointment_intake_fields` | 4 |
| `INSURANCE_INTAKE` | `update_appointment_intake_fields` | 1 |
| `HUMAN_HANDOFF` | `queue_staff_handoff`, `notify_on_call` | 2 |
| `wrap_up` | *(none — goodbye / summary)* | 0 |

#### Full tool catalog (all 14 names)

| # | Tool | Backend | Used in nodes |
|---|------|---------|---------------|
| 1 | `lookup_patient` | EHR | `PATIENT_IDENTIFY`, `VERIFY_RETURNING` |
| 2 | `get_patient_profile` | EHR | `VERIFY_RETURNING` |
| 3 | `create_shell_patient` | EHR | `REGISTER_SHELL_PROFILE` |
| 4 | `get_department_policies` | EHR/config | `CLINICAL_ROUTE` |
| 5 | `note_chief_complaint` | EHR/orchestrator | `CLINICAL_ROUTE` |
| 6 | `search_providers` | EHR | `SCHEDULING` |
| 7 | `get_availability` | EHR | `SCHEDULING` |
| 8 | `book_appointment` | EHR | `CONFIRM_COMMIT` only |
| 9 | `reschedule_appointment` | EHR | `CONFIRM_COMMIT` |
| 10 | `cancel_appointment` | EHR | `CONFIRM_COMMIT` |
| 11 | `update_appointment_intake_fields` | EHR | `CONFIRM_COMMIT`, `INSURANCE_INTAKE` |
| 12 | `retrieve_kb` | RAG | `RAG_ANSWER` |
| 13 | `queue_staff_handoff` | Ops | `HUMAN_HANDOFF` |
| 14 | `notify_on_call` | Ops | `HUMAN_HANDOFF` |

*Not in node allowlists:* `end_session` — orchestrator calls gateway directly to hang up.

**Key rule:** `book_appointment` / `reschedule_appointment` / `cancel_appointment` are **not** in `SCHEDULING` — only in `CONFIRM_COMMIT`.

---

### Q: System prompt on top, then nodes, then LLM + tools inside each node?

**Short answer:** **Yes — that's the design.** Three layers stack together every time the LLM runs (in nodes that use the LLM).

```
┌─────────────────────────────────────────────────────────┐
│  LAYER 1 — Global system prompt (always, whole call)    │
│  "You are Mercy General voice receptionist…             │
│   short spoken replies… no diagnosis… voice tone…"      │
└─────────────────────────────────────────────────────────┘
                          +
┌─────────────────────────────────────────────────────────┐
│  LAYER 2 — Outer node (orchestrator picks ONE)          │
│  e.g. active_node = SCHEDULING                          │
└─────────────────────────────────────────────────────────┘
                          +
┌─────────────────────────────────────────────────────────┐
│  LAYER 3 — Inner (inside that node, each LLM turn)      │
│  • Node prompt: "You are finding slots; do NOT book yet"│
│  • Allowed tools: search_providers, get_availability  │
│  • Conversation history (user + assistant messages)     │
│  • Tool results (if LLM called a tool this turn)        │
└─────────────────────────────────────────────────────────┘
                          ↓
                    LLM responds (and maybe calls tools)
```

#### What each layer does

| Layer | What it is | Changes when? |
|-------|------------|---------------|
| **Global system prompt** | Identity + rules for the **whole call** (hospital name, voice style, never diagnose, emergency awareness) | Same for entire session |
| **Outer node** | Which **step** you're on (`PATIENT_IDENTIFY`, `SCHEDULING`, …) | Orchestrator advances when step is complete |
| **Node prompt + tools** | **Extra instructions + tool menu** for that step only | Changes every time outer node changes |

Design doc wording: orchestrator sends **`system + node prompt, user text, allowed_tools`** to the LLM ([03-component-orchestration.md](../../system%20design/03-component-orchestration.md) §4).

#### What you have in code today

`src/orchestrator/graph.py` → **Layer 1 only** (`SYSTEM_PROMPT`).

`src/orchestrator/__init__.py` → adds that prompt once per session, then appends user/assistant messages.

**Not built yet:** outer nodes (Layer 2), node prompts, or tools (Layer 3).

#### Nodes with no LLM at all

These skip Layer 3 entirely — no LLM turn, no tools:

- `session_start`, `EMERGENCY_GATE`, `PLAY_911_SCRIPT`, `wrap_up` (mostly fixed logic/script)

All other conversational nodes use **Layer 1 + Layer 2 + Layer 3** together.

---

### Q: Are nodes separate agents?

**Short answer:** **No.** In this design, nodes are **not** separate agents. It is **one agent** (one LLM, one conversation memory) wearing **different hats** depending on which node the orchestrator says you're in.

| Wrong mental model | Correct mental model |
|--------------------|----------------------|
| 13 nodes = 13 separate AI agents | **1 agent** + **13 workflow steps** |
| Each node has its own brain / memory | **Same brain**, same chat history; only **prompt + tools** change |
| Agent A hands off to Agent B | Orchestrator code says: "now you're in scheduling mode" |

#### One receptionist, different tasks

Same person answers the phone the whole call. When they're collecting ID, they ask ID questions. When they're scheduling, they check the calendar. **Same person** — different **task sheet** for that moment.

That task sheet = **node prompt + tool allowlist**.

#### What actually changes when the node changes

| Stays the same | Changes per node |
|----------------|------------------|
| One LLM model (e.g. GPT-4o) | Node-specific instructions |
| One session / conversation history | Which tools are allowed |
| Global system prompt (Mercy General rules) | What the orchestrator will let you do next |

#### Why not separate agents per node?

Separate agents would mean:

- Split memory — scheduling agent wouldn't know what ID agent learned unless you pass state manually
- Harder to keep one natural phone conversation
- More cost / latency (spin up different agent configs)
- Weaker safety — a "scheduling agent" could skip verification if not coordinated

This design avoids that: **orchestrator owns the roadmap**; **one LLM handles language** inside each step.

#### LangGraph implementation note

In code, each outer node can be a **LangGraph node function** — but that is a **code organization** unit, not a separate AI agent. Typically:

```text
One compiled graph
  ├── node function: patient_identify  → calls same LLM + identify prompt + lookup tools
  ├── node function: scheduling        → calls same LLM + scheduling prompt + calendar tools
  └── node function: confirm_commit    → calls same LLM + confirm prompt + book tools
```

Same `ChatOpenAI` instance. Same message list. Different wrapper per step.

#### When you *would* use separate agents

Multi-agent patterns (supervisor + specialist agents) are a **different architecture**. This project explicitly chose **single orchestrator + single LLM in nodes** for trust and control ([03-component-orchestration.md](../../system%20design/03-component-orchestration.md): "LLM provides language understanding **inside** nodes—not global unconstrained control").

---

### Q: Do prompt and tools change with each step of communication?

**Short answer:** **Almost — but be precise:**

- **Prompt + tools change** when you move to a **new outer node** (new workflow step).
- **They stay the same** across many **back-and-forth messages** while you remain in the **same node**.

Global system prompt stays the same the **whole call**.

#### Two kinds of "step"

| Kind | Example | Prompt / tools change? |
|------|---------|------------------------|
| **Message turn** (one user speaks, agent replies) | User: "Tuesday works" → Agent: "What time?" | **No** — still same node, same prompt, same tools |
| **Outer node change** (workflow advances) | Finished ID → move to `SCHEDULING` | **Yes** — new node prompt + new tool menu |

#### Example: staying in `SCHEDULING` (many messages, same setup)

```
Node = SCHEDULING  (prompt + tools unchanged for all of this)

Turn 1: User "I need a cardiologist"     → LLM + search_providers, get_availability
Turn 2: User "How about next week?"      → LLM + get_availability  (same tools)
Turn 3: User "Tuesday 2pm with Dr. Patel"→ LLM speaks (same tools)
Turn 4: User "Yes that's the one"        → orchestrator decides: move to CONFIRM_COMMIT
```

Turns 1–3: **same node prompt, same tools**, only **chat history** grows.

Turn 4: outer node changes → **new prompt + new tools** (`book_appointment` now allowed).

#### What changes every LLM turn vs only on node change

| Every message (every turn) | Only when outer node changes |
|----------------------------|------------------------------|
| User's new words (STT text) | Node-specific prompt |
| Conversation history grows | Tool allowlist |
| Tool results from this turn (if any) | What orchestrator checks before advancing |
| Emergency gate re-runs (outer check before inner) | — |

**Global system prompt:** set once at `session_start`, **never** changes mid-call.

#### One-line summary

> **Same node = same hat (prompt + tools), many conversations.**  
> **New node = new hat.**

---

### Q: Graph starts with global agent, it picks the node, node talks, then next node?

**Short answer:** **Close, but one fix:** the **global prompt does NOT decide which node to move to.** The **orchestrator code** (rules) picks the node. The LLM only **talks inside** the current node.

#### What you got right

- Call starts → global system prompt is loaded once
- System is in **one node at a time**
- That node runs the LLM to communicate with the user (maybe many turns)
- When the step is done → move to **next node** → communicate there

#### The important correction

| Who | Job |
|-----|-----|
| **Global prompt** | Tells the LLM *who it is* and *global rules* (Mercy General, no diagnosis, short voice replies). It does **not** pick nodes. |
| **Orchestrator (Python/LangGraph code)** | Picks **active node**, runs **emergency gate**, checks **when step is complete**, **advances** to next node |
| **LLM inside a node** | Talks to user, may call **allowed tools** — does **not** freely jump to another node |

The LLM is **not** a "manager agent" that discusses "which node should we go to?" That would be unsafe (model could skip ID check or book too early).

#### Full call flow (correct order)

```
1. session_start
   → orchestrator creates session, loads global system prompt into memory

2. EMERGENCY_GATE (every user message, first)
   → code checks keywords — NOT the main LLM deciding

3. Active node = PATIENT_IDENTIFY
   → orchestrator sends: global prompt + node prompt + tools + user text
   → LLM talks ("What's your name and date of birth?")
   → maybe calls lookup_patient
   → repeat until orchestrator rules say: "ID step complete"

4. Orchestrator advances (code, not LLM)
   → active node = VERIFY_RETURNING or REGISTER_SHELL_PROFILE

5. LLM talks in THAT node (new node prompt + new tools)
   → many turns possible...

6. Orchestrator advances again
   → CLINICAL_ROUTE → SCHEDULING → CONFIRM_COMMIT → ...

7. wrap_up → end call
```

#### Simple picture

```
ORCHESTRATOR (boss — code)          LLM (worker — one brain)
        │                                    │
        │ "You are in SCHEDULING now"          │
        ├──────────────────────────────────►│ talks + tools
        │                                    │
        │ user speaks again (still scheduling)│
        ├──────────────────────────────────►│ talks + tools (same node)
        │                                    │
        │ "Step done → go to CONFIRM_COMMIT"  │
        ├──────────────────────────────────►│ talks + different tools
        │                                    │
```

**Boss = orchestrator. Worker = LLM.** Global prompt is the worker's **employee handbook**, not the boss.

#### Your sentence, corrected

> ~~Graph starts from global agent with prompt, then that will discuss which node to move~~  
> **Graph starts → global prompt loaded → orchestrator sets first node → LLM communicates inside that node → orchestrator moves to next node when rules pass → LLM communicates in next node → …**

---

### Q: How does the system start and move? (before session, global prompt, first node)

**Short answer:** The LLM is **not running** the moment you connect. Voice connects first. Global prompt is **loaded into memory** when the orchestrator is first needed (first user message today, or optional greeting). **Orchestrator code** always knows the first node — the LLM does not "wake up and pick" where to go.

#### Timeline — from browser open to first reply

**Phase A — Connect (no LLM yet)**

```
User opens /client → clicks connect → POST /webrtc/offer
  → CallSession created (session_id assigned)
  → WebRTC audio + Deepgram STT + TTS wired up
  → session_start (design): save session_id, active_node = PATIENT_IDENTIFY
```

**What exists in memory now:**
- `session_id`
- Voice pipeline (mic in, speaker out)
- **No LLM call yet** in current code
- **No global prompt in LLM yet** in current code (waits for first transcript)

**Phase B — First time we need the LLM**

Two common patterns (design can use either):

| Pattern | When global prompt loads | Who speaks first |
|---------|--------------------------|------------------|
| **A — User speaks first** (current code) | First STT final → `handle_transcript` | User talks, then agent replies |
| **B — Agent greets first** (future option) | Right after `session_start` | Agent: "Mercy General, how can I help?" |

**Current code (`src/orchestrator/__init__.py`):**

```text
First user message arrives
  → if new session: messages = [SystemMessage(global SYSTEM_PROMPT)]   ← global prompt added HERE
  → append user text
  → LLM.invoke(messages)
  → reply → TTS → user hears it
```

Global prompt is **prepended to the message list once** — not a separate "global agent" that runs first and picks a node.

**Phase C — Every user message after that (the loop)**

```text
1. User speaks → STT → merged text
2. EMERGENCY_GATE (code checks keywords — before LLM)
   → if emergency: play 911 script, end (no normal LLM flow)
3. Orchestrator knows: active_node = e.g. PATIENT_IDENTIFY
4. Build LLM input:
     • global system prompt (already in message list)
     • + node prompt for PATIENT_IDENTIFY
     • + allowed tools (lookup_patient)
     • + full conversation history
     • + new user text
5. LLM replies (maybe calls tools)
6. Reply → TTS → user hears
7. Orchestrator checks: is PATIENT_IDENTIFY complete?
     • NO  → stay in PATIENT_IDENTIFY (next message repeats step 1–6, same node)
     • YES → active_node = VERIFY_RETURNING or REGISTER_SHELL_PROFILE (code decides)
8. Next user message uses NEW node prompt + NEW tools
```

**Phase D — End**

```text
INSURANCE_INTAKE done → active_node = wrap_up → goodbye → end_session → clear memory
```

#### What is NOT happening at start

| Myth | Reality |
|------|---------|
| Global prompt LLM runs alone and chooses first node | Orchestrator **hardcodes** first node after `session_start` → `EMERGENCY_GATE` → `PATIENT_IDENTIFY` |
| LLM runs at WebRTC connect | Only voice/STT/TTS connect; LLM waits for text |
| New LLM instance per node | **Same** message history + same model; node prompt/tools swap |

#### Memory over the call (one bucket)

```text
messages = [
  SystemMessage(global prompt),      ← added once, stays forever
  HumanMessage("I need an appointment"),
  AIMessage("Sure, are you a returning patient?"),
  HumanMessage("Yes, John Smith"),
  ...                                ← grows every turn
]
```

When node changes, orchestrator **updates** which node prompt + tools are sent on the **next** invoke — it does not wipe chat history.

#### Start → move in 5 lines

1. **Connect** — voice only, orchestrator sets `active_node = PATIENT_IDENTIFY`
2. **First text** — load global prompt + run LLM in first node
3. **Loop** — user speaks → emergency check → LLM in current node
4. **Move** — when code says step done, change `active_node`, swap node prompt + tools
5. **End** — `wrap_up`, clear session

#### Today vs full design

| Piece | Today (code) | Full design (not built) |
|-------|--------------|-------------------------|
| Connect | ✅ WebRTC session | ✅ + `session_start` state |
| Global prompt | ✅ on first user message | ✅ same (+ optional greet) |
| First node | ❌ implicit single `chat` node | ✅ `PATIENT_IDENTIFY` |
| Emergency gate | ❌ only text in global prompt | ✅ code before every turn |
| Node move | ❌ never moves | ✅ orchestrator rules |
| Tools | ❌ none | ✅ per-node allowlist |

---

### Q: User says "Hello" → text → who receives it? LangGraph?

**Short answer:** **Not LangGraph first.** The **voice gateway** (`CallSession`) receives audio and gets text from Deepgram STT. Then it calls **`handle_transcript`** in the orchestrator. **That function** then calls LangGraph.

LangGraph is step **4** in the chain, not step **1**.

#### Full chain today (you say "Hello")

```
YOU (mic)
  ↓ audio
WebRTC / CallSession          ← src/gateway/session.py
  ↓
Deepgram STT                  ← src/adapters/stt_deepgram.py
  ↓ text: "Hello"
CallSession._on_transcript
  ↓ (waits ~1.2s to merge utterances)
CallSession._get_assistant_response("Hello")
  ↓ builds event { session_id, text: "Hello" }
handle_transcript(event)      ← src/orchestrator/__init__.py  ★ orchestrator entry
  ↓ first message? add global SYSTEM_PROMPT
  ↓ append HumanMessage("Hello")
LangGraph graph.ainvoke()     ← src/orchestrator/graph.py  ★ LLM runs here
  ↓ returns AIMessage reply
handle_transcript returns text string
  ↓
CallSession.speak(text)       ← TTS → you hear agent voice
```

#### Who is who

| Component | File | Role when you say "Hello" |
|-----------|------|---------------------------|
| **Gateway / CallSession** | `session.py` | Owns the call; routes audio and text |
| **Deepgram STT** | `stt_deepgram.py` | Turns voice → `"Hello"` |
| **Orchestrator entry** | `orchestrator/__init__.py` → `handle_transcript` | **First code that sees the text** for the brain; prepares messages |
| **LangGraph** | `orchestrator/graph.py` | Runs the LLM on those messages; today = one `chat` node |
| **TTS** | `tts_*` | Turns reply text → audio |

**Wiring:** `server.py` connects them:

```python
CallSession(assistant_handler=handle_transcript, ...)
```

So: gateway hears you → orchestrator `handle_transcript` → LangGraph → back to gateway → TTS.

#### Full design (future) — same entry, more steps inside orchestrator

When you say "Hello", **gateway still delivers text to `handle_transcript`**. Inside orchestrator, **before** LangGraph:

```text
handle_transcript("Hello")
  1. EMERGENCY_GATE (code — no emergency)
  2. check active_node (e.g. PATIENT_IDENTIFY)
  3. build prompts + tools for that node
  4. LangGraph / LLM invoke
  5. return reply
```

LangGraph is still the **LLM runner** inside the orchestrator — not the thing that receives WebRTC/STT directly.

#### One line

> **STT text → Gateway → `handle_transcript` (orchestrator) → LangGraph (LLM) → Gateway → TTS**

---

Think of the **outer graph** as a **fixed roadmap** for the phone call. At any moment the system is in **exactly one node** — one step on that roadmap.

Examples of nodes:

| Node | Meaning (plain English) |
|------|-------------------------|
| `PATIENT_IDENTIFY` | “We are still figuring out who is calling.” |
| `SCHEDULING` | “Identity is done; we are finding doctors and time slots.” |
| `CONFIRM_COMMIT` | “User picked a slot; we need a clear yes before we book.” |
| `RAG_ANSWER` | “User asked a hospital FAQ; answer from KB, then go back to routing.” |

**Who moves between nodes?** The **orchestrator** (Python/LangGraph code), **not** the LLM freely choosing “I’ll skip to booking now.”

The outer graph answers: *“What phase of the call are we in, and what are we allowed to do next at a policy level?”*

See [node-diagrams.md](./node-diagrams.md) — that file is **outer only** (no tools on purpose).

---

#### Inner loop = LLM + tools inside one node

While you stay in **one** outer node (e.g. `SCHEDULING`), the **LLM** handles the **conversation**: listen, ask follow-ups, speak naturally.

When it needs **facts or actions**, it calls **tools** (function calls) — but **only** from that node’s **allowlist** in [tools.md](./tools.md) §3.

Examples:

| In node `SCHEDULING` | Allowed inner tools |
|----------------------|---------------------|
| Yes | `search_providers`, `get_availability` |
| No | `book_appointment` (blocked until `CONFIRM_COMMIT`) |

So **inner** = “LLM turn loop + tool calls **inside** the current node.”

The LLM can call **zero, one, or many** tools in one turn, then reply to the caller — **without** leaving `SCHEDULING` yet.

---

#### One concrete example (booking a visit)

```
OUTER (orchestrator moves these steps):
  PATIENT_IDENTIFY → VERIFY_RETURNING → CLINICAL_ROUTE → SCHEDULING → CONFIRM_COMMIT → wrap_up

INNER (inside SCHEDULING only — LLM may repeat this many times):
  User: "I need Dr. Chen next week"
  → LLM calls search_providers(...)
  → LLM calls get_availability(...)
  → LLM: "I have Tuesday 2pm or Thursday 10am with Dr. Patel — which works?"
  (still in SCHEDULING — no booking yet)

OUTER transition (orchestrator decides):
  User: "Tuesday 2pm, yes book it"
  → orchestrator moves to CONFIRM_COMMIT

INNER (inside CONFIRM_COMMIT):
  → LLM reads back summary
  → User: "Yes, book it"
  → LLM calls book_appointment(...)   ← only now this tool exists
```

**Why split?** So the model cannot skip identity check, cannot book without confirmation, and cannot ignore emergency keywords — the **outer** graph enforces order; the **inner** tools fetch real data instead of hallucinating slots.

---

#### Simple analogy

| Layer | Analogy |
|-------|---------|
| **Outer graph** | Hospital reception **workflow script**: “First ID, then reason for visit, then schedule, then confirm.” |
| **Inner (LLM + tools)** | The **receptionist** talking to the patient **during** one step — but they can only use certain **buttons** (lookup chart, check calendar) depending on which step they’re on. |

---

#### What you have in code today

`src/orchestrator/graph.py` is **only inner-ish**: one `chat` node with **no outer roadmap** and **no tools**. Real design = outer nodes from `tools.md` §1 + inner allowlists from §3.

**Related:** [tools.md](./tools.md) §0 (nodes vs tools), §1 (outer nodes), §2–3 (tool catalog + allowlists); [03-component-orchestration.md](../../system%20design/03-component-orchestration.md) §2 (outer), §4 (inner loop).

---

### Q: Where does the LLM live — node vs tools?

**Short answer:** **Yes — the node has the LLM.** The LLM is what **talks** to the caller. **Tools do not talk** and do not have an LLM. Tools are **backend actions** the LLM **calls** when it needs data (lookup patient, check slots, book appointment).

So the picture is:

```
OUTER NODE (e.g. SCHEDULING)
├── LLM          ← speaks to user, understands speech, decides what to say next
├── node prompt  ← "You are in scheduling; collect slot preference; do not book yet"
└── tools        ← optional function calls the LLM may invoke (allowlisted for this node only)
       ├── search_providers  → calls EHR API, returns JSON
       └── get_availability  → calls EHR API, returns JSON
```

**Inner** does **not** mean “tools only.” **Inner** means “everything that happens **while we stay in one node**” — and that **includes the LLM**.

| Piece | Has LLM? | Job |
|-------|----------|-----|
| **Node** (most of them) | **Yes** | Run the LLM with a **node-specific** system prompt + conversation history |
| **Tool** | **No** | Run Python/API code; return structured result to the LLM |
| **Orchestrator** (outer graph code) | **No** | Pick active node, validate tool calls, advance to next node when rules pass |

---

#### What one turn looks like inside a node

1. User speaks → STT → text arrives at orchestrator.
2. Orchestrator sees active node = `SCHEDULING`.
3. Orchestrator sends to **LLM**: node prompt + user text + **allowed tools list**.
4. LLM either:
   - **Replies in plain text** (“What day works for you?”) — **no tool call**, or
   - **Calls a tool** (`get_availability(...)`) → orchestrator runs it → result goes **back to the same LLM** → LLM then speaks (“I have Tuesday at 2pm…”).
5. Text goes to TTS → user hears the agent.

The **LLM always produces the words the patient hears** (except a few special nodes below). Tools only supply **facts** so the LLM does not make up doctor names or times.

---

#### Nodes that do **not** use the LLM (exceptions)

Most nodes = **LLM + tools**. A few are **orchestrator-only** (no LLM conversation loop):

| Node | LLM? | Why |
|------|------|-----|
| `EMERGENCY_GATE` | No | Keyword/classifier check — hard rule, must be fast and deterministic |
| `PLAY_911_SCRIPT` | No | Fixed script, then end call |
| `session_start` | No | Bootstrap session state |
| `wrap_up` | Maybe minimal | Often fixed goodbye + summary; can be LLM or template |

Everything like `PATIENT_IDENTIFY`, `SCHEDULING`, `RAG_ANSWER`, etc. **uses the LLM to communicate**.

---

#### Why `tools.md` separates “outer nodes” and “inner tools”

It is **not** saying “nodes = no LLM, tools = LLM.”

It is saying:

| Term in doc | Really means |
|-------------|----------------|
| **Outer graph / nodes** | **Which step** of the call; **which tools are allowed**; **when to advance** |
| **Inner tools** | **Extra capabilities** the LLM inside that node may call — not a separate speaker |

The LLM is **inside the node**, not inside each tool.

---

#### Tiny mental model

- **Node** = room you are standing in (`SCHEDULING` room).
- **LLM** = receptionist in that room who talks to the patient.
- **Tools** = phone on the wall in that room (call EHR, call RAG) — only certain phones work in certain rooms.

Same receptionist (LLM) in every conversational node; different room (node) = different script + different phones allowed (tools).

---

#### Tie to current code

In `src/orchestrator/graph.py` today there is **one** node called `chat` and it **is** the LLM — no tools yet, no other outer nodes. That is a minimal version of “node contains LLM.” Full design adds **many outer nodes**, each running **the same LLM pattern** but with different prompts and tool menus.


## Questions

- ~~What is “outer” vs “inner”?~~ → answered above (2026-05-31)
- ~~Does the node have the LLM or only tools?~~ → answered above (2026-05-31)

*(List open questions; strike through or move to Notes when resolved.)*


## Decisions

- **2026-05-31:** Next phase = **per-node plans** (prompt + tools + enter/exit), using [tools.md](./tools.md) allowlists before LangGraph implementation replaces stub `chat` node.
