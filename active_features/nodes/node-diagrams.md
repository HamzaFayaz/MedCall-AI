# Orchestrator Node Diagrams

This file is a diagram-only companion to [tools.md](./tools.md). It follows the current system design without changing node or tool definitions.

---

## Complete Agent Flow — Nodes Only

This diagram shows the outer orchestrator flow only. It intentionally does **not** show tools.

```mermaid
flowchart TD
  session_start["session_start"]
  emergency_gate["EMERGENCY_GATE"]
  play_911_script["PLAY_911_SCRIPT"]
  patient_identify["PATIENT_IDENTIFY"]
  verify_returning["VERIFY_RETURNING"]
  register_shell_profile["REGISTER_SHELL_PROFILE"]
  clinical_route["CLINICAL_ROUTE"]
  rag_answer["RAG_ANSWER"]
  scheduling["SCHEDULING"]
  confirm_commit["CONFIRM_COMMIT"]
  insurance_intake["INSURANCE_INTAKE"]
  wrap_up["wrap_up"]
  human_handoff["HUMAN_HANDOFF"]

  session_start --> emergency_gate
  emergency_gate -->|emergency detected| play_911_script
  emergency_gate -->|no emergency| patient_identify
  patient_identify -->|returning patient| verify_returning
  patient_identify -->|new patient| register_shell_profile
  verify_returning --> clinical_route
  register_shell_profile --> clinical_route
  clinical_route -->|policy or FAQ question| rag_answer
  rag_answer --> clinical_route
  clinical_route --> scheduling
  scheduling --> confirm_commit
  confirm_commit --> insurance_intake
  insurance_intake --> wrap_up
  play_911_script --> wrap_up

  patient_identify -.->|fallback trigger| human_handoff
  verify_returning -.->|fallback trigger| human_handoff
  register_shell_profile -.->|fallback trigger| human_handoff
  clinical_route -.->|fallback trigger| human_handoff
  scheduling -.->|fallback trigger| human_handoff
  confirm_commit -.->|fallback trigger| human_handoff
  insurance_intake -.->|fallback trigger| human_handoff
  human_handoff --> wrap_up
```

---

## Per-Node Tool Diagrams

These diagrams mirror the current tool allowlists in [tools.md](./tools.md). Nodes with no LLM tools are shown explicitly.

### `session_start`

```mermaid
flowchart TD
  session_start["session_start"] --> no_tools["No LLM tools"]
```

### `EMERGENCY_GATE`

```mermaid
flowchart TD
  emergency_gate["EMERGENCY_GATE"] --> no_tools["No LLM tools"]
```

### `PLAY_911_SCRIPT`

```mermaid
flowchart TD
  play_911_script["PLAY_911_SCRIPT"] --> no_tools["No LLM tools"]
```

### `PATIENT_IDENTIFY`

```mermaid
flowchart TD
  patient_identify["PATIENT_IDENTIFY"] --> lookup_patient["lookup_patient"]
```

### `VERIFY_RETURNING`

```mermaid
flowchart TD
  verify_returning["VERIFY_RETURNING"] --> lookup_patient["lookup_patient"]
  verify_returning --> get_patient_profile["get_patient_profile"]
```

### `REGISTER_SHELL_PROFILE`

```mermaid
flowchart TD
  register_shell_profile["REGISTER_SHELL_PROFILE"] --> create_shell_patient["create_shell_patient"]
```

### `CLINICAL_ROUTE`

```mermaid
flowchart TD
  clinical_route["CLINICAL_ROUTE"] --> get_department_policies["get_department_policies"]
  clinical_route --> note_chief_complaint["note_chief_complaint"]
```

### `SCHEDULING`

```mermaid
flowchart TD
  scheduling["SCHEDULING"] --> search_providers["search_providers"]
  scheduling --> get_availability["get_availability"]
```

### `CONFIRM_COMMIT`

```mermaid
flowchart TD
  confirm_commit["CONFIRM_COMMIT"] --> book_appointment["book_appointment"]
  confirm_commit --> reschedule_appointment["reschedule_appointment"]
  confirm_commit --> cancel_appointment["cancel_appointment"]
  confirm_commit --> update_appointment_intake_fields["update_appointment_intake_fields"]
```

### `RAG_ANSWER`

```mermaid
flowchart TD
  rag_answer["RAG_ANSWER"] --> retrieve_kb["retrieve_kb"]
```

### `INSURANCE_INTAKE`

```mermaid
flowchart TD
  insurance_intake["INSURANCE_INTAKE"] --> update_appointment_intake_fields["update_appointment_intake_fields"]
```

### `wrap_up`

```mermaid
flowchart TD
  wrap_up["wrap_up"] --> no_tools["No LLM tools"]
```

### `HUMAN_HANDOFF`

```mermaid
flowchart TD
  human_handoff["HUMAN_HANDOFF"] --> queue_staff_handoff["queue_staff_handoff"]
  human_handoff --> notify_on_call["notify_on_call"]
```

---

## Tool Association Note

`end_session` is listed in the tool catalog in [tools.md](./tools.md), but it is described there as possibly orchestrator-direct rather than an LLM tool. It is therefore not shown as an allowlisted LLM tool for a node in these diagrams.
