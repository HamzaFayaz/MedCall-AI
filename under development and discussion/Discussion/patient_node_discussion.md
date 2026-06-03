# PATIENT_IDENTIFY — discussion

Working notes for **`PATIENT_IDENTIFY` only**.

Build this node first. **`VERIFY_RETURNING`** and **`REGISTER_SHELL_PROFILE`** are separate discussions after identify is done.

Part of **Component 03 — Sub-plan 02** (after LangGraph step 0 refactor).

---

## Related files

| File | Role |
|------|------|
| [tools.md](./tools.md) | Node purpose + tool allowlist |
| [node-diagrams.md](./node-diagrams.md) | Flow diagram |
| [orchestrator-discuss.md](./orchestrator-discuss.md) | General orchestrator discussion |
| [system design/03-component-orchestration.md](../../system%20design/03-component-orchestration.md) | Canonical orchestration design |
| [PRD.md](../../PRD.md) §5 Feature 2, §6 State 1 | Returning patient auth |
| [system design/04-component-backend-ehr.md](../../system%20design/04-component-backend-ehr.md) | EHR API (not built yet) |
| [src/orchestrator/state.py](../../src/orchestrator/state.py) | Current session fields |
| [currently_working_on.md](../../currently_working_on.md) | Active work order |

---

## Where this node sits

```text
session_start
  → EMERGENCY_GATE (every utterance)
       └─ clear → PATIENT_IDENTIFY   ← we are here
                    ├─ lookup hit     → VERIFY_RETURNING   (build later)
                    └─ new / not found → REGISTER_SHELL_PROFILE   (build later)
```

**Prerequisite:** Sub-plan 02 **step 0** — LangGraph refactor (`session_start`, `EMERGENCY_GATE`, thin `handle_transcript`).

**Out of scope for this discussion:** verify node, register node, clinical route, full EHR API.

---

## Node spec (target)

| Field | Value |
|-------|--------|
| **Node ID** | `PATIENT_IDENTIFY` |
| **LLM** | Yes |
| **Tool** | `lookup_patient` only |
| **Purpose** | Who is calling? Returning or new? Collect name + DOB + phone; run lookup when complete. |
| **PRD tie-in** | Feature 2 — Patient Authentication; PRD State 1 |

### Plan checklist

- [ ] Node prompt (must do / must not do)
- [ ] When `lookup_patient` may run
- [ ] Enter conditions
- [ ] Exit conditions (code decides next node)
- [ ] State fields written during this node

---

## Who speaks first?

**v1 (current design): patient speaks first.**

```text
Call connects
  → session_start (code only — no TTS, no LLM)
  → active_node = PATIENT_IDENTIFY
  → agent silent until first user message
  → patient speaks
  → EMERGENCY_GATE
  → PATIENT_IDENTIFY LLM → agent reply
  → back-and-forth until exit
```

- First spoken reply is **after** the first patient utterance (no connect greeting in v1).
- This node stays active across **multiple turns** until exit conditions are met.

**Open (product):** Optional greeting on connect (*"Mercy General, how can I help?"*) — still `PATIENT_IDENTIFY`, but agent breaks silence first.

---

## Lookup fields (confirmed)

Uploaded by `scripts/migrate_to_supabase.py` into `patients`:

- `first_name`, `last_name`, `dob`, `phone` (required for `lookup_patient`)
- `mrn`, `id` — system IDs, not collected from caller on this node

---

## The one tool for this node

| Tool | EHR endpoint | When |
|------|--------------|------|
| `lookup_patient` | `GET /patients/lookup?first_name&last_name&dob&phone` | All three identity fields collected |

**Not allowed in this node:**

- `get_patient_profile` — no PHI until verify path (next node)
- `create_shell_patient` — register node
- Booking, RAG, scheduling tools

---

## Open questions — decide for `PATIENT_IDENTIFY` only

### 1. What to collect before lookup?

**Decided (2026-06-03):** Verify with **`first_name` + `last_name` + `dob` + `phone`** — matches `patients` table and `scripts/migrate_to_supabase.py`. **Not age** (age is only in `clinical_data`, derived from DOB).

| Field | On call | In Supabase `patients` |
|-------|---------|------------------------|
| Full name | Legal name spoken | `first_name`, `last_name` |
| DOB | Date of birth (not “I’m 34”) | `dob` (`DATE`, from FHIR `birthDate`) |
| Phone | Phone number | `phone` |

**Also (design):**

- Returning vs new patient?
- Calling for self vs someone else? (always collect **patient** identity)

| Question | Options |
|----------|---------|
| Question order | Fixed script vs LLM-driven conversation |
| Partial / wrong fields | **Stay** in `PATIENT_IDENTIFY` — ask again (see §1b) |
| Match found (exactly 1) | Exit to `VERIFY_RETURNING` |
| Not found (0), caller said returning | **Stay** — re-ask / correct fields (do not register yet) |
| Not found (0), caller said new | Exit to `REGISTER_SHELL_PROFILE` |

**Flow:**

1. Patient speaks first → agent responds.
2. Ask returning or new.
3. Collect patient **full name, date of birth, phone**.
4. When all three complete → `lookup_patient(first_name, last_name, dob, phone)`.
5. Code routes per lookup result table (§1b).

---

### 1b. Lookup results — when not all three match

**Rule:** `lookup_patient` requires **all three fields correct together**. There is no “1 of 3 correct → proceed.” The tool returns a **count**, not partial credit.

| Result | Meaning | What the system does | Next node |
|--------|---------|----------------------|-----------|
| **Fields incomplete** | Missing name, DOB, or phone | LLM asks for the missing piece | **Stay** `PATIENT_IDENTIFY` |
| **0 matches** | None of the triple exists in DB (or all three wrong) | If **returning**: say not found, ask to repeat/correct name, DOB, or phone (ASR typo common). If **new**: offer registration. | **Stay** (returning) or **REGISTER** (new, after confirm) |
| **1 match** | Full triple matches one row | **Code** sets `active_node = VERIFY_RETURNING` + `patient_id` (see §3b) | **VERIFY_RETURNING** |
| **2+ matches** | Ambiguous (data quality issue) | Do not load PHI. Ask clarifying question (e.g. spell last name, repeat DOB). | **Stay** `PATIENT_IDENTIFY` |

**“One correct, two wrong”** — the DB query does not run until all three are collected. After lookup:

- You get **0 matches** (treat as “combination wrong”) → **do not** jump to verify; **ask again**.
- You do **not** tell the caller *which* field was wrong (security / no enumeration).
- Script example: *"I couldn't find a record with that information. Could you repeat your date of birth and phone number?"*

**Do not move to another node when:**

- Only 1–2 fields collected
- Lookup returned 0 but caller said **returning** (retry first, max ~2 attempts then offer handoff or new registration)
- Lookup returned 2+ rows
- Caller is correcting a field mid-node

**When to move to `REGISTER_SHELL_PROFILE`:**

- Caller clearly said **new patient**, or
- Returning path: not found after **retry budget** (e.g. 2 lookup attempts), and caller agrees to register

**When to move to `VERIFY_RETURNING`:**

- Only when lookup returns **exactly one** `patient_id`

---

### 2. Who calls `lookup_patient`?

| Approach | Notes |
|----------|-------|
| LLM calls tool | Flexible; risk of early/wrong calls |
| Code only | Deterministic; needs structured fields in state |
| **Hybrid (draft)** | LLM converses; code or gated tool when `identity_fields` complete |

---

### 3. Exit rules (this node only)

Orchestrator **code** advances `active_node` — LLM does not pick the next node. See §1b for lookup outcomes.

| Exit to | Condition (code) |
|---------|------------------|
| `VERIFY_RETURNING` | `lookup_status = matched` (exactly one row) |
| `REGISTER_SHELL_PROFILE` | `patient_type = new` **or** returning + not found + retry exhausted + user agrees |
| Stay in `PATIENT_IDENTIFY` | Incomplete fields, 0 match (retry), 2+ matches, caller correcting |
| `PLAY_911_SCRIPT` | `EMERGENCY_GATE` hit (every utterance) |

**Done with this node when:** exactly one match **or** routed to register after rules above.

---

### 3b. How control moves to the next node (not the LLM)

**The LLM does not choose the next node.** Orchestrator **code** (graph node function or router after tool result) updates `active_node`.

**When `lookup_patient` returns exactly one row:**

```text
Turn N (still PATIENT_IDENTIFY until step 5)
  1. User message arrives
  2. EMERGENCY_GATE
  3. Graph runs patient_identify node
  4. LLM may call lookup_patient → tool returns { patient_id, count: 1 }
  5. CODE (after tool):
       - state.patient_id = <id>
       - state.lookup_status = "matched"
       - state.active_node = "VERIFY_RETURNING"   ← handoff here
  6. Spoken reply this turn (pick one implementation):
       A) Short bridge from identify: "Thanks, I found your record. One moment."
       B) Re-invoke with VERIFY prompt same turn (heavier)
       C) No extra line — next user message uses VERIFY node (simplest v1)

Turn N+1
  1. User speaks (e.g. "yes")
  2. EMERGENCY_GATE
  3. Graph runs verify_returning node (because active_node changed)
  4. LLM gets VERIFY node prompt: "Is this Keisha Kris, born March 15, 1989?"
  5. get_patient_profile after user confirms
```

**Split of responsibility:**

| Step | `PATIENT_IDENTIFY` | `VERIFY_RETURNING` |
|------|--------------------|--------------------|
| Collect name, DOB, phone | Yes | No |
| DB lookup (all 3 match) | Yes (`lookup_patient`) | Optional re-lookup only if disputed |
| **Confirm identity with caller** | No (only "found a record" at most) | **Yes** — "Is this …?" |
| Load clinical profile | No | Yes (`get_patient_profile`) |

So **yes — when record is found, control must move to the next node.** The old prompt line meant a **optional short spoken bridge**, not "stay in identify and do full verify here." Full confirm happens in **`VERIFY_RETURNING`**.

**LangGraph shape (after step 0 refactor):**

```text
patient_identify node
  → conditional edge on lookup_status
       matched      → verify_returning
       not_found    → patient_identify (retry) OR register_shell_profile
       ambiguous    → patient_identify
```

---

### 4. EHR dependency for v1

Only need **`lookup_patient`** for this node.

| Option | Notes |
|--------|-------|
| EHR API first | Block until Component 04 |
| **Mock / Supabase adapter (draft)** | Thin tool interface; swap when EHR ready |

---

### 5. Voice UX

| Topic | Notes |
|-------|-------|
| ASR errors | Confirm spelling: *"I heard … is that correct?"* |
| DOB | Normalize spoken date → structured field in state |
| Reply length | 1–3 sentences (spoken) |
| Privacy | Don't read MRN/SSN; minimal confirm at this stage |

---

## Prompt layers for this node

Every LLM turn is built from **three layers** (not one blob):

| Layer | What | `PATIENT_IDENTIFY` |
|-------|------|---------------------|
| **1. Global** | Mercy General voice receptionist rules | Same on all nodes — today `SYSTEM_PROMPT` in `graph.py` |
| **2. Emergency backup** | Short block on **every** LLM node | **Yes** — see below (not a separate node) |
| **3. Node prompt** | Only this step’s job | Identity collection + lookup behavior |

**What is NOT in the node prompt:**

- **`EMERGENCY_GATE`** — Python keywords run **before** the LLM every message (sub-plan 01). No LLM, no prompt.
- **`PLAY_911_SCRIPT`** — fixed TTS string from code (`EMERGENCY_SCRIPT`), not LLM-generated.

**Why emergency appears twice:**

```text
User message
  → EMERGENCY_GATE (keywords) ──hit──► 911 script, end (LLM never runs)
  → clear
  → PATIENT_IDENTIFY LLM gets: global + emergency backup + node prompt
       → if model catches missed emergency → trigger_emergency (tool) → same 911 path
       → else normal identify conversation
```

Per [orchestrator-discuss.md](./orchestrator-discuss.md): backup on **all** LLM nodes, not only this one. Keyword gate stays the real enforcement; prompt backup is defense in depth.

**v1 emergency backup block** (repeat in every LLM node, or keep once in global — node may repeat for emphasis):

```text
EMERGENCY (backup): If the caller describes a possible medical emergency (chest pain,
difficulty breathing, severe bleeding, stroke signs, suicidal intent, etc.) — even if
phrased unusually — do NOT continue identification, scheduling, or triage. Call
trigger_emergency immediately. Do not only tell them to call 911 in chat without
calling the tool.
```

**Tools on this node:** `lookup_patient`, `trigger_emergency` (orchestrator-only — ends session like keyword gate).

---

## Full prompt draft — `PATIENT_IDENTIFY` (v0)

What the LLM sees (layers 1–3 combined for implementation):

```text
[GLOBAL]
You are the automated voice receptionist for Mercy General Hospital in Seattle.
Keep replies short (1-3 sentences) for spoken conversation.
You help with scheduling, registration, and general front-desk questions.
Do not diagnose, prescribe, or give medical advice.

[EMERGENCY BACKUP]
If the caller describes a possible medical emergency (chest pain, difficulty breathing,
severe bleeding, stroke signs, suicidal intent, etc.) — even if phrased unusually —
do NOT continue this step. Call trigger_emergency immediately.

[NODE: PATIENT_IDENTIFY]
You are identifying who is calling.

Your job this step:
- Ask if they are a returning patient or new to Mercy General.
- Collect the PATIENT's full legal name, date of birth, and phone number (not age alone —
  ask for date of birth if they only give age).
- If they are calling for someone else, collect the patient's details, not only the caller's.
- When you have all three fields, use lookup_patient.
- If lookup returns not_found: do not say which field was wrong. Ask them to repeat or
  confirm their name, date of birth, and phone. If they said they are new, or after retries
  offer registration.
- If lookup returns one match: you may say briefly that a record was found (e.g. "Thanks,
  I found your record."). Do NOT read chart details here — the system moves to verification
  next; another step will ask "Is this [name], born [date]?"
- Keep one question at a time when possible. Be polite and brief for voice.

Do NOT in this step:
- Discuss symptoms, diagnosis, or treatment.
- Load or mention medical history, medications, or chart details.
- Book or offer appointment times.
- Create a new patient record (registration is a later step).

Tools: lookup_patient (when name, DOB, phone are ready), trigger_emergency (emergency only).
```

Orchestrator still enforces: tool allowlist, exit routing, retry count — prompt alone does not change nodes.

---

## State fields (this node only)

| Field | Purpose |
|-------|---------|
| `active_node` | `"PATIENT_IDENTIFY"` while in this step |
| `caller_is_self` | Optional — self vs calling for someone else |
| `patient_type` | `"returning"` \| `"new"` \| unknown |
| `identity_fields` | `{ full_name, dob, phone }` — partial until complete |
| `lookup_status` | `pending` \| `matched` \| `not_found` \| `ambiguous` |
| `lookup_attempts` | Count retries after `not_found` (cap e.g. 2) |
| `patient_id` | Set only when `lookup_status = matched` (verify node confirms) |

Fields like full profile, registration payload → **later nodes**.

---

## Discussion log

### 2026-06-03 — Scope narrowed

**Decision:** This file covers **`PATIENT_IDENTIFY` only**. Build it first; verify and register nodes later.

### 2026-06-03 — Patient speaks first (confirmed)

v1: no agent greeting on connect. First agent speech after first patient message.

### 2026-06-03 — Tools

This node: **`lookup_patient` only**. Other tools belong to later nodes.

### 2026-06-03 — Auth fields locked

**Lookup key:** full name + **DOB** + phone (not age). Data confirmed in `patients` table via `migrate_to_supabase.py`.

### 2026-06-03 — Partial / failed lookup behavior

**All three must match together.** 0 or 2+ results → **stay** in `PATIENT_IDENTIFY` and ask again (returning). Do not reveal which field was wrong. Register node only after new-patient path or retries exhausted.

### 2026-06-03 — Prompt layers

**Global + emergency backup + node prompt.** `EMERGENCY_GATE` is code before LLM, not in node prompt. Emergency backup block on every LLM node; `trigger_emergency` tool recommended. Full draft in § "Full prompt draft".

**Still to decide:**

1. Greeting on connect — yes or no?
2. Hybrid vs LLM-only for `lookup_patient`?
3. Mock tool vs wait for EHR API?

<!-- Add dated sections below as we decide -->

---

### Q: How does control go from `PATIENT_IDENTIFY` to `VERIFY_RETURNING` or `REGISTER_SHELL_PROFILE`?

**A:**

The **LLM does not choose** the next node. **Python / LangGraph code** does, after each user message, using fields in session state (especially `active_node` and `lookup_status`).

**Every user message (same pattern):**

```text
1. User speaks → STT text
2. EMERGENCY_GATE (code) — if hit → 911, stop
3. Read state.active_node  →  e.g. "PATIENT_IDENTIFY"
4. Run ONLY that node's graph function (that node's prompt + tools)
5. After tools / rules, CODE updates state.active_node if exit conditions met
6. Return spoken reply to TTS
```

**While in `PATIENT_IDENTIFY`:**

- LLM collects name, DOB, phone and may call `lookup_patient`.
- Tool returns: **0 rows**, **1 row**, or **2+ rows** (not "which field was wrong").

**CODE decides next node (not the model):**

| `lookup_patient` result | Also consider | CODE sets `active_node` to |
|-------------------------|---------------|----------------------------|
| **1 row** | Caller said returning | `VERIFY_RETURNING` + save `patient_id` |
| **0 rows** | Caller said **new** patient | `REGISTER_SHELL_PROFILE` |
| **0 rows** | Caller said **returning** | stay `PATIENT_IDENTIFY` (ask again; retry count) |
| **0 rows** | Returning + retries used up + user agrees to register | `REGISTER_SHELL_PROFILE` |
| **2+ rows** | — | stay `PATIENT_IDENTIFY` (clarify spelling / DOB) |
| Fields not complete yet | — | stay `PATIENT_IDENTIFY` |

**Next user message:** step 3 reads the **new** `active_node`, so the **verify** or **register** node function runs (different prompt, different tools).

**Example — found record:**

```text
Turn 5: active_node = PATIENT_IDENTIFY
        User gives name, DOB, phone
        lookup_patient → 1 match, patient_id = abc-123
        CODE: active_node = VERIFY_RETURNING, patient_id = abc-123
        Agent may say: "Thanks, I found your record."

Turn 6: active_node = VERIFY_RETURNING   ← control already moved
        VERIFY node prompt runs
        Agent: "Is this Keisha Kris, born March 15, 1989?"
        User: "Yes" → get_patient_profile → later CLINICAL_ROUTE
```

**Example — new patient:**

```text
User: "I'm a new patient"
CODE may set patient_type = new → skip lookup or 0 is OK
CODE: active_node = REGISTER_SHELL_PROFILE
Next turn: REGISTER node collects demographics + create_shell_patient
```

**LangGraph (after step 0 refactor):** one compiled graph; `patient_identify` node has **conditional edges** on `lookup_status` / `patient_type` → edge to `verify_returning` or `register_shell_profile` or loop back to self.

**Remember:** `active_node` in state is the map. Who moves the map? **Orchestrator code** after rules — never the LLM saying "let's go to verify now."

---

### Q: Where is the implementation plan?

**A:** [.agent/Plans/03_orchestrator_02_langgraph_patient_identify.md](../../.agent/Plans/03_orchestrator_02_langgraph_patient_identify.md) (Component 03 sub-plan 02). Indexed in [03_orchestrator_cards.md](../../.agent/Plans/03_orchestrator_cards.md). Nine commits: CallState → prompts → lookup → graph step 0 → PATIENT_IDENTIFY → thin adapter → tests → progress.

---

### Q: Was sub-plan 02 implemented?

**A (2026-06-03):** Yes — see plan status **Complete**. Built: `call_state.py`, `prompts.py`, `tools/lookup_patient.py`, `graph.py` + `routing.py` + `nodes/` (`session_start`, `emergency_gate`, `play_911`, `patient_identify`, verify/register stubs), thin `handle_transcript` in `__init__.py`, tests `test_graph_emergency.py` / `test_patient_identify.py`. Code sets `active_node` after `lookup_patient` count; LLM does not route.
