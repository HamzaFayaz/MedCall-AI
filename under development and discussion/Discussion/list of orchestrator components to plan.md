# List of orchestrator components to plan

**Context:** Read [orchestrator-discuss.md](./orchestrator-discuss.md) first (outer vs inner, flow, `handle_transcript`, LangGraph, emergency hybrid, terminal testing).

**Implementation plans:** [.agent/Plans/03_orchestrator_cards.md](../../.agent/Plans/03_orchestrator_cards.md) (Component 03 index) · [03_orchestrator_01_session_start_emergency_gate.md](../../.agent/Plans/03_orchestrator_01_session_start_emergency_gate.md) (sub-plan 01)

**Sources:** [tools.md](./tools.md) · [node-diagrams.md](./node-diagrams.md) · [03-component-orchestration.md](../../system%20design/03-component-orchestration.md)

**Per-node plan fields:** node prompt · tools · enter · exit · LLM yes/no

---

## 1. Outer graph nodes (13)

| # | Node ID | LLM | Tools |
|---|---------|-----|-------|
| 1 | `session_start` | No | No |
| 2 | `EMERGENCY_GATE` | No | No |
| 3 | `PLAY_911_SCRIPT` | No | No |
| 4 | `PATIENT_IDENTIFY` | Yes | Yes |
| 5 | `VERIFY_RETURNING` | Yes | Yes |
| 6 | `REGISTER_SHELL_PROFILE` | Yes | Yes |
| 7 | `CLINICAL_ROUTE` | Yes | Yes |
| 8 | `RAG_ANSWER` | Yes | Yes |
| 9 | `SCHEDULING` | Yes | Yes |
| 10 | `CONFIRM_COMMIT` | Yes | Yes |
| 11 | `INSURANCE_INTAKE` | Yes | Yes |
| 12 | `HUMAN_HANDOFF` | Yes | Yes |
| 13 | `wrap_up` | No* | No |

*`wrap_up` may use template only or minimal LLM — product choice.

**Not a design node:** `chat` — current code stub in `src/orchestrator/graph.py` only.

---

## 2. LLM tools (14) — by tool → node(s)

| Tool | Node(s) |
|------|---------|
| `lookup_patient` | `PATIENT_IDENTIFY`, `VERIFY_RETURNING` |
| `get_patient_profile` | `VERIFY_RETURNING` |
| `create_shell_patient` | `REGISTER_SHELL_PROFILE` |
| `get_department_policies` | `CLINICAL_ROUTE` |
| `note_chief_complaint` | `CLINICAL_ROUTE` |
| `search_providers` | `SCHEDULING` |
| `get_availability` | `SCHEDULING` |
| `book_appointment` | `CONFIRM_COMMIT` |
| `reschedule_appointment` | `CONFIRM_COMMIT` |
| `cancel_appointment` | `CONFIRM_COMMIT` |
| `update_appointment_intake_fields` | `CONFIRM_COMMIT`, `INSURANCE_INTAKE` |
| `retrieve_kb` | `RAG_ANSWER` |
| `queue_staff_handoff` | `HUMAN_HANDOFF` |
| `notify_on_call` | `HUMAN_HANDOFF` |

### Orchestrator-only (not in node LLM allowlists)

| Action | Used by |
|--------|---------|
| `end_session` | `wrap_up`, `PLAY_911_SCRIPT`, emergency path — gateway/orchestrator direct |
| `trigger_emergency` *(planned)* | All LLM nodes — backup after keyword gate; see [orchestrator-discuss.md](./orchestrator-discuss.md) |

---

## 3. Tools — by node → tool(s)

| Node | Tools |
|------|-------|
| `session_start` | — |
| `EMERGENCY_GATE` | — |
| `PLAY_911_SCRIPT` | — |
| `PATIENT_IDENTIFY` | `lookup_patient` |
| `VERIFY_RETURNING` | `lookup_patient`, `get_patient_profile` |
| `REGISTER_SHELL_PROFILE` | `create_shell_patient` |
| `CLINICAL_ROUTE` | `get_department_policies`, `note_chief_complaint` |
| `RAG_ANSWER` | `retrieve_kb` |
| `SCHEDULING` | `search_providers`, `get_availability` |
| `CONFIRM_COMMIT` | `book_appointment`, `reschedule_appointment`, `cancel_appointment`, `update_appointment_intake_fields` |
| `INSURANCE_INTAKE` | `update_appointment_intake_fields` |
| `HUMAN_HANDOFF` | `queue_staff_handoff`, `notify_on_call` |
| `wrap_up` | — |

---

## 4. Plan status — nodes

### Planned (all nodes — write plan before implement)

- [ ] `session_start`
- [ ] `EMERGENCY_GATE`
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

### In process

- [ ] `session_start` → [.agent/Plans/03_orchestrator_01_session_start_emergency_gate.md](../../.agent/Plans/03_orchestrator_01_session_start_emergency_gate.md)
- [ ] `EMERGENCY_GATE` → same sub-plan 01

### Complete

*(none yet)*

### Not started (implementation)

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

---

## 5. Plan status — cross-cutting (not a node)

| Item | Status | Reference |
|------|--------|-----------|
| Replace stub `chat` node with full LangGraph graph | Not started | [orchestrator-discuss.md](./orchestrator-discuss.md) |
| `handle_transcript` — emergency gate before LLM | Not started | [orchestrator-discuss.md](./orchestrator-discuss.md) |
| Terminal text tester (`handle_transcript` CLI) | Not started | [orchestrator-discuss.md](./orchestrator-discuss.md) |
| `trigger_emergency` orchestrator tool (LLM backup) | Planned | [orchestrator-discuss.md](./orchestrator-discuss.md) |
| Session state persistence (`active_node`, `patient_id`, …) | Not started | [03-component-orchestration.md](../../system%20design/03-component-orchestration.md) §8 |

---

## 6. Happy-path order (reference)

`session_start` → `EMERGENCY_GATE` → `PATIENT_IDENTIFY` → `VERIFY_RETURNING` | `REGISTER_SHELL_PROFILE` → `CLINICAL_ROUTE` ↔ `RAG_ANSWER` → `SCHEDULING` → `CONFIRM_COMMIT` → `INSURANCE_INTAKE` → `wrap_up`

**Side paths:** `PLAY_911_SCRIPT` · `HUMAN_HANDOFF`
