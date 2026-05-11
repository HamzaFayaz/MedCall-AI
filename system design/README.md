# System design — Mercy General Voice Agent

This folder is the **architecture source** for the production-oriented voice intake and scheduling system described in [`PRD.md`](../PRD.md). It translates product requirements into deployable components, control flows, and trust boundaries.

## Documents

| # | Document | What it covers |
|---|----------|----------------|
| 1 | [`01-main-system-design.md`](01-main-system-design.md) | End-to-end architecture, context diagram, deployment, call lifecycle sequence, trust principles |
| 2 | [`02-component-voice-realtime.md`](02-component-voice-realtime.md) | WebRTC, signaling, media, STT/TTS streaming, latency budget |
| 3 | [`03-component-orchestration.md`](03-component-orchestration.md) | Flow-based orchestration, emergency gate, tool-calling inside nodes, state machine |
| 4 | [`04-component-backend-ehr.md`](04-component-backend-ehr.md) | API gateway pattern, `ehr_server` responsibilities, API contracts at a glance |
| 5 | [`05-component-data-rag.md`](05-component-data-rag.md) | Supabase usage, pgvector RAG pipeline, data minimization for LLM context |
| 6 | [`06-trust-security-operations.md`](06-trust-security-operations.md) | Security, privacy, auditability, SLOs, failure modes, human handoff |

## Architectural stance (summary)

- **Primary transport:** WebRTC for real-time bidirectional audio.
- **Orchestration:** **Flow / node graph** on the outside (predictable phases and confirmations); **tool-calling LLM** inside nodes for natural language and tool use.
- **Safety:** **Emergency screening** runs on **every** speech segment before normal graph advancement.
- **Production posture:** Encryption in transit, structured audit events, idempotent writes, health checks, and explicit human escalation—designed so operations and compliance reviewers can trace behavior.

Start with **01-main-system-design.md**, then read component docs in order.
