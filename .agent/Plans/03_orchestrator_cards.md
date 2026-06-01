# Component 03: Orchestration — plan index

Parent plan for **conversation orchestration** (LangGraph outer graph + per-node LLM/tools).

**Design:** [system design/03-component-orchestration.md](../../system%20design/03-component-orchestration.md)  
**Discussion:** [under development and discussion/Discussion/orchestrator-discuss.md](../../under%20development%20and%20discussion/Discussion/orchestrator-discuss.md)  
**Checklist:** [list of orchestrator components to plan.md](../../under%20development%20and%20discussion/Discussion/list%20of%20orchestrator%20components%20to%20plan.md)  
**Nodes & tools:** [tools.md](../../under%20development%20and%20discussion/Discussion/tools.md) · [node-diagrams.md](../../under%20development%20and%20discussion/Discussion/node-diagrams.md)

---

## Sub-plans (components of Component 03)

| # | Plan | Nodes | Status |
|---|------|-------|--------|
| **01** | [03_orchestrator_01_session_start_emergency_gate.md](./03_orchestrator_01_session_start_emergency_gate.md) | `session_start`, `EMERGENCY_GATE` (+ minimal `PLAY_911_SCRIPT` path) | In process |
| 02 | *(not started)* | `PATIENT_IDENTIFY`, `VERIFY_RETURNING`, `REGISTER_SHELL_PROFILE` | Planned |
| 03 | *(not started)* | `CLINICAL_ROUTE`, `RAG_ANSWER` | Planned |
| 04 | *(not started)* | `SCHEDULING`, `CONFIRM_COMMIT` | Planned |
| 05 | *(not started)* | `INSURANCE_INTAKE`, `HUMAN_HANDOFF`, `wrap_up` | Planned |
| 06 | *(not started)* | Cross-cutting: full LangGraph graph, `trigger_emergency`, terminal CLI | Planned |

---

## All 13 outer nodes (reference)

`session_start` → `EMERGENCY_GATE` → `PATIENT_IDENTIFY` → `VERIFY_RETURNING` | `REGISTER_SHELL_PROFILE` → `CLINICAL_ROUTE` ↔ `RAG_ANSWER` → `SCHEDULING` → `CONFIRM_COMMIT` → `INSURANCE_INTAKE` → `wrap_up`

Side paths: `PLAY_911_SCRIPT`, `HUMAN_HANDOFF`
