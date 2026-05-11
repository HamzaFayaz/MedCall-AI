<!-- markdownlint-disable MD013 MD060 -->

# Design gaps and remediation backlog

This document lists **issues worth addressing** in the Mercy General voice-agent architecture, with **concrete remediation detail**. It was derived by **cross-checking** [`problems_with_the_system_design.md`](problems_with_the_system_design.md) against the canonical specs ([`01-main-system-design.md`](01-main-system-design.md) through [`06-trust-security-operations.md`](06-trust-security-operations.md)).

**Scope:** Gaps where the official design is silent, thin, or needs hardening—not repeating claims that already contradict the written architecture (e.g. emergency handling is already specified as keyword + optional classifier in [`03-component-orchestration.md`](03-component-orchestration.md); AEC is already called out in [`02-component-voice-realtime.md`](02-component-voice-realtime.md)).

Use this file as a **backlog** when you are ready to deepen production readiness.

---

## 1. Scalability and deployment

### 1.1 Gap

[`01-main-system-design.md`](01-main-system-design.md) shows logical tiers (edge, app, data) but does **not** specify horizontal scaling: replica counts, load balancers, autoscaling signals (CPU, custom metrics such as concurrent sessions), or rollout strategy (blue/green, canaries).

### 1.2 Remediation (detail)

- **Define a reference deployment** (e.g. Kubernetes or managed containers): minimum pods per service for HA, pod disruption budgets, and health probes wired to [`04-component-backend-ehr.md`](04-component-backend-ehr.md) `/healthz` and `/readyz`.
- **Autoscaling:** HPA (or cloud equivalent) on realtime gateway using **custom metric** `active_webrtc_sessions` or request rate on session creation; separate HPA for orchestrator and EHR API based on CPU and queue depth if you add internal queues.
- **Stateful edge:** If the gateway holds sticky session state, document **session affinity** or move ephemeral state to Redis so any gateway instance can resume with orchestrator + store ([`03-component-orchestration.md`](03-component-orchestration.md) §8).
- **Load testing:** Formal test plan (bursty connects, packet loss) already hinted in [`02-component-voice-realtime.md`](02-component-voice-realtime.md); add pass/fail thresholds tied to SLOs in [`06-trust-security-operations.md`](06-trust-security-operations.md) §5.

---

## 2. Disaster recovery and backups

### 2.1 Gap

[`06-trust-security-operations.md`](06-trust-security-operations.md) mentions read replica failover in a runbook outline but does **not** define backup frequency, retention, **RTO/RPO**, or multi-region strategy for Supabase data, Supabase vectors, and application state.

### 2.2 Remediation (detail)

- **Supabase:** Enable **PITR** (point-in-time recovery) if available on your plan; document backup retention and restore drill (quarterly).
- **RPO/RTO targets:** Example starter: RPO ≤ 15 minutes for appointment data, RTO ≤ 1 hour for full stack in primary region—tune after risk review.
- **Supabase Vector / RAG:** Define whether vectors are rebuildable from source artifacts; if yes, document rebuild pipeline; if no, include the vector table in backup scope.
- **Orchestrator Redis (if used):** Classify as **cache vs durability**; if durable session recovery depends on it, enable persistence (AOF/RDB) or accept “reconnect may lose in-flight dialogue” and document UX.
- **Runbook:** One-page restore order: DNS → gateway → orchestrator → EHR → verify `/readyz`.

---

## 3. Human handoff and contact center

### 3.1 Gap

[`03-component-orchestration.md`](03-component-orchestration.md) §7 describes handoff triggers and a conceptual `queue_staff_queue` but not **vendor integration** (e.g. Twilio Flex, Amazon Connect), **ANI/DNIS**, ticket creation, or **context package** (transcript summary, patient id, reason code) delivered to the agent desktop.

### 3.2 Remediation (detail)

- **Choose integration pattern:** (A) PSTN transfer to published queue number, (B) task router API enqueue with attributes, or (C) CRM case creation + callback.
- **Context bundle:** Structured JSON: `session_id`, `handoff_reason`, `patient_id` (if verified), **redacted or summarized transcript**, last orchestrator node, failed intents count—align with PHI policy in [`06-trust-security-operations.md`](06-trust-security-operations.md) §3.
- **Idempotency:** If handoff creates a ticket, use idempotency key on webhook to avoid duplicates on client retry.
- **Graceful close:** After handoff accepted, end AI session per existing `session.end` contract ([`02-component-voice-realtime.md`](02-component-voice-realtime.md) §3).

---

## 4. Database and EHR API operations

### 4.1 Gap

[`04-component-backend-ehr.md`](04-component-backend-ehr.md) emphasizes validation and idempotency but does **not** specify **connection pooling** (e.g. PgBouncer, pool size per worker), **read replica** routing for read-heavy paths, or **index list** for `/patients/lookup`, availability queries, and appointments.

### 4.2 Remediation (detail)

- **Pooling:** Size pools from expected FastAPI worker count × concurrent requests; cap connections to stay under Supabase/Postgres limits; expose pool saturation metrics.
- **Read paths:** Route `GET /providers`, `GET /providers/availability`, and idempotent reads to replica when **staleness** (few seconds) is acceptable; keep **all commits** on primary.
- **Indexes:** Add explicit migration list: e.g. `(last_name, dob, phone)` for lookup; `(provider_id, date)` for availability; `(patient_id, start_time)` for appointments—validate with `EXPLAIN` on slow queries.
- **Optional cache:** The doc mentions short TTL cache; define keys, invalidation on write, and cache bypass for commit verification paths.

---

## 5. WebRTC edge cases (NAT / TURN)

### 5.1 Gap

[`02-component-voice-realtime.md`](02-component-voice-realtime.md) describes signaling and a 1:1 gateway; it notes SFU for scale but does **not** spell out **STUN/TURN** when symmetric NAT or strict firewalls block direct media.

### 5.2 Remediation (detail)

- **ICE servers:** Configure STUN (public) and **TURN** (credentials from secrets manager) on the client `RTCPeerConnection`; log ICE failure reasons (non-PHI) for support.
- **Operational:** TURN relay increases latency—monitor percentage of **relay vs host/srflx** candidates; set alerts if relay rate spikes regionally.
- **v1 vs later:** For internal pilot, document “supported networks”; for general patient population, TURN is usually mandatory.

---

## 6. Session recovery and orchestrator durability

### 6.1 Gap

[`03-component-orchestration.md`](03-component-orchestration.md) §8 and [`02-component-voice-realtime.md`](02-component-voice-realtime.md) §6 mention persistence for reconnect but not **end-to-end behavior**: what is restored after gateway restart, duplicate transcript handling, and **exactly-once** vs **at-least-once** for tool calls.

### 6.2 Remediation (detail)

- **State snapshot:** Persist `session_id`, current node, filled slots, `patient_id`, pending confirmation tokens, and last processed `utterance_id`.
- **Dedup:** Gateway should stamp monotonic `utterance_id` on each final transcript; orchestrator ignores replays.
- **Tool idempotency:** Already required for EHR writes ([`03-component-orchestration.md`](03-component-orchestration.md) §6); extend to any side-effecting gateway actions.
- **TTL:** Align Redis/session TTL with max call length + buffer; document “session expired” UX and handoff offer.

---

## 7. LLM and tool-call hardening (beyond allowlists)

### 7.1 Gap

[`06-trust-security-operations.md`](06-trust-security-operations.md) and [`03-component-orchestration.md`](03-component-orchestration.md) rely on **allowlists** and orchestrator validation; there is **no** explicit requirement for **schema validation** of tool arguments (e.g. Pydantic), **output sanitization** before TTS, or **rate limits** on LLM calls per session.

### 7.2 Remediation (detail)

- **Tool args:** Define JSON Schema or Pydantic models per tool; reject malformed calls before hitting EHR; log structured reject reason.
- **Model output:** Strip or escape unexpected control characters; cap response length for TTS; block patterns that look like tool JSON leakage to the user channel.
- **Rate limits:** Per-`session_id` token budget and per-IP session creation (complements [`02-component-voice-realtime.md`](02-component-voice-realtime.md) checklist).
- **Prompt injection:** Treat as **risk reduction**, not elimination—combine allowlists, minimization ([`01-main-system-design.md`](01-main-system-design.md) §7), and monitoring for anomalous tool attempt patterns.

---

## 8. Observability (prescriptive stack)

### 8.1 Gap

[`01-main-system-design.md`](01-main-system-design.md) and [`02-component-voice-realtime.md`](02-component-voice-realtime.md) list goals and example metrics but not a **single chosen stack** (e.g. OpenTelemetry → collector → backend, log aggregation, dashboard templates).

### 8.2 Remediation (detail)

- **Tracing:** OpenTelemetry SDK in gateway, orchestrator, EHR; propagate `trace_id` on `transcript_event` and EHR calls; sample rate tuned for cost.
- **Metrics:** Histograms for time-to-first-text, time-to-first-audio, STT/TTS errors, emergency gate latency, handoff count.
- **Logs:** Structured JSON, correlation id, **no raw PHI** per [`06-trust-security-operations.md`](06-trust-security-operations.md) §3; centralize (vendor choice is flexible).
- **Dashboards:** One “voice health” dashboard and one “booking integrity” dashboard (idempotency conflicts, 409/duplicate detection).

---

## 9. Compliance and commercial (non-architecture but required for healthcare)

### 9.1 Gap

Architecture docs describe technical controls; **BAAs**, subprocessors, and **data processing agreements** with STT/LLM/TTS vendors are **out of band** but required for HIPAA-aligned operation.

### 9.2 Remediation (detail)

- Maintain a **vendor matrix**: PHI flow per vendor, BAA status, region, retention, and subprocessors.
- Map technical controls ([`06-trust-security-operations.md`](06-trust-security-operations.md)) to policy: audit log retention, transcript storage decision, encryption standards.
- Legal/compliance sign-off gate before production PHI.

---

## 10. Accessibility and language

### 10.1 Gap

Product goals in [`01-main-system-design.md`](01-main-system-design.md) do not include **captions**, **multi-language**, or **TTY** paths.

### 10.2 Remediation (detail)

- **Captions:** If a visual client exists, stream partial/final STT to UI; privacy and latency requirements documented.
- **Languages:** Define supported locale list; STT/TTS model pairing per locale; orchestrator prompts and emergency scripts translated and reviewed.
- **TTY/relay:** If required by jurisdiction or hospital policy, define alternate channel or handoff to voice relay service.

---

## 11. Implementation guardrails (verify behavior matches design)

These are **not** missing from the written design, but are common implementation drift risks:

| Topic | Design source | What to verify in build |
|--------|----------------|-------------------------|
| Emergency path | [`03-component-orchestration.md`](03-component-orchestration.md) §3 | Keyword layer always on; classifier optional; tests for PRD keyword list |
| Barge-in | [`02-component-voice-realtime.md`](02-component-voice-realtime.md) §5 | Client VAD/AEC enabled; `speak.cancel` honored under load |
| Secrets | [`01`](01-main-system-design.md), [`06`](06-trust-security-operations.md) §4 | No production secrets in repo; rotation runbook executed |
| Booking commits | [`03`](03-component-orchestration.md) §6 | `book_*` only in `CONFIRM_COMMIT`; idempotency headers on all writes |

---

## Suggested priority (for planning only)

| Priority | Items |
|----------|--------|
| **P0** | §6 Session recovery + dedup; §7 Tool schema validation; §11 Emergency/booking guardrails |
| **P1** | §1 Scaling reference; §4 DB pooling/indexes; §8 Observability stack; §5 TURN |
| **P2** | §2 DR numbers and drills; §3 Contact center; §9 Vendor matrix; §10 Accessibility |

Adjust priorities with product scope (pilot vs general availability).

---

## Related documents

- Canonical architecture: [`README.md`](README.md), [`01-main-system-design.md`](01-main-system-design.md)
- Prior critique (uncalibrated): [`problems_with_the_system_design.md`](problems_with_the_system_design.md)
