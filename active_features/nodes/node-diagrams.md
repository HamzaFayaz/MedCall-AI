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

## Node And Tool Responsibilities

This section explains each node in the agent flow, followed by the tools available inside that node.

### `session_start`

**Node work:** Starts the voice session, attaches the `session_id`, and loads any persisted orchestrator state if the session is being resumed.

**Tools:** No LLM tools.

### `EMERGENCY_GATE`

**Node work:** Runs before graph advancement on every finalized user utterance. It checks for emergency language and routes emergency cases to `PLAY_911_SCRIPT`.

**Tools:** No LLM tools. This node is deterministic, with an optional internal classifier service outside the LLM tool allowlist.

### `PLAY_911_SCRIPT`

**Node work:** Plays the emergency script, records the emergency event for audit, and moves the session toward termination.

**Tools:** No LLM tools.

### `PATIENT_IDENTIFY`

**Node work:** Determines whether the caller is calling for themself or someone else, and whether the patient is returning or new. It collects identifying fields such as name, date of birth, and phone when needed.

**Tools:**

- `lookup_patient`: Looks up a patient by completed identity fields, such as name, date of birth, and phone.

### `VERIFY_RETURNING`

**Node work:** Verifies a returning patient and loads the verified patient context before clinical routing.

**Tools:**

- `lookup_patient`: Confirms the patient exists and resolves the patient record.
- `get_patient_profile`: Loads token-efficient clinical context after successful verification.

### `REGISTER_SHELL_PROFILE`

**Node work:** Collects the minimum required demographics and insurance information for a new patient, then creates a shell patient profile.

**Tools:**

- `create_shell_patient`: Creates the new patient shell profile after required fields are collected.

### `CLINICAL_ROUTE`

**Node work:** Collects the reason for visit, identifies routing needs such as acute versus chronic concerns, captures chief complaint context, and determines whether policy or FAQ help is needed.

**Tools:**

- `get_department_policies`: Reads referral, department, and booking policy notes used for safe routing.
- `note_chief_complaint`: Persists chief complaint and duration information for the pre-brief or appointment context.

### `RAG_ANSWER`

**Node work:** Answers scoped policy or FAQ questions using the knowledge base, then returns control to `CLINICAL_ROUTE`.

**Tools:**

- `retrieve_kb`: Retrieves approved knowledge-base content for safe FAQ, policy, and routing language.

### `SCHEDULING`

**Node work:** Searches providers and available slots, presents scheduling options, and handles cross-coverage UX. It does not commit bookings.

**Tools:**

- `search_providers`: Finds providers by name, specialty, or department.
- `get_availability`: Gets provider availability and slot options with server-side scheduling rules.

### `CONFIRM_COMMIT`

**Node work:** Presents the canonical appointment summary, requires explicit user confirmation, and performs appointment mutations only after confirmation.

**Tools:**

- `book_appointment`: Books a confirmed appointment with idempotency protection.
- `reschedule_appointment`: Reschedules an existing appointment after confirmation.
- `cancel_appointment`: Cancels an existing appointment after confirmation.
- `update_appointment_intake_fields`: Updates appointment-related intake fields when booking and intake persistence are split.

### `INSURANCE_INTAKE`

**Node work:** Collects insurance and logistics information needed after appointment confirmation and persists it to appointment context.

**Tools:**

- `update_appointment_intake_fields`: Saves insurance and intake fields on the appointment or related record.

### `wrap_up`

**Node work:** Gives the final confirmation summary and ends the normal conversation flow.

**Tools:** No LLM tools.

### `HUMAN_HANDOFF`

**Node work:** Handles fallback or escalation when staff support is needed, such as user request, repeated ASR failure, out-of-scope needs, or backend exhaustion.

**Tools:**

- `queue_staff_handoff`: Creates or queues a staff handoff request.
- `notify_on_call`: Optionally notifies an on-call person or escalation channel.

---

## Tool Association Note

`end_session` is listed in the tool catalog in [tools.md](./tools.md), but it is described there as possibly orchestrator-direct rather than an LLM tool. It is therefore not shown as an allowlisted LLM tool for a node in these diagrams.
