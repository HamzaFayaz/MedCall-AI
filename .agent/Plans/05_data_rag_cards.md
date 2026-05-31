# Component 05: Data + RAG Layer - Build Handoff

Use this file as the starting context for the next chat/window.

Primary design reference: `system design/05-component-data-rag.md`.

Related top-level references:

- `PRD.md`
- `system design/01-main-system-design.md`
- `system design/04-component-backend-ehr.md`
- `docs/doctors.md`
- `data/knowledge_base/README.md`

## Current Decision

RAG is not an open medical-advice system. It is a hospital policy and care-routing retrieval layer.

The selected vector store is **Supabase PostgreSQL with `pgvector`**, not ChromaDB or Pinecone.

The model planned for orchestration/conversation is **GPT-4o**. GPT-4o can reason over user language, but hospital facts must come from tools or retrieved approved KB content.

## What RAG Is For

Use RAG for:

- Hospital FAQ
- Parking, hours, locations, contact information
- Insurance and billing policy wording
- Referral requirements and department booking rules
- Appointment preparation instructions
- Symptom-to-department routing guidance
- Emergency red-flag wording and escalation scripts

RAG answers should be grounded in retrieved chunks and should not diagnose, prescribe, recommend treatment, or promise clinical outcomes.

## What RAG Is Not For

Do not put these in RAG:

- Doctor availability
- Appointment slots
- Patient identity
- Patient clinical profile
- Current medications, allergies, conditions, or visit history
- Booking, cancellation, or reschedule confirmation
- Live insurance eligibility
- Referral status

Those belong behind structured Supabase/EHR API tools.

## Approved RAG Data Files

Only ingest these files:

- `data/knowledge_base/mercy_general_operational_policy.md`
- `data/knowledge_base/department_services.md`
- `data/knowledge_base/symptom_department_routing_guide.md`
- `data/knowledge_base/faq_and_call_scripts.md`

Do not ingest:

- `data/knowledge_base/README.md`
- `docs/rag_external_data_sources.md`
- `data/healthcare_qa.csv`
- `clinic_knowledge_base.md`
- archived files under `older system design/`

`data/healthcare_qa.csv` is a real downloaded dataset, but it only has 51 rows and is now treated as legacy/reference data, not the primary RAG source.

## Current Data State

The curated Mercy General KB has already been created.

`department_services.md` is aligned with the current provider departments in `docs/doctors.md`:

- Primary Care
- Emergency Medicine
- Pediatrics
- Women's Health / OB-GYN
- Cardiology
- Orthopedics and Sports Medicine
- General Surgery
- Gastroenterology
- Neurology
- Psychiatry

The routing guide intentionally avoids unavailable departments. If a caller asks for Dermatology or Urology style concerns, the KB routes to Primary Care or front desk/external referral help because those departments are not in the current Mercy General doctor directory.

## Structured Tools Needed Later

Doctor and scheduling data should be fetched through tools, not RAG.

Expected provider/scheduling tools:

- `search_providers(name?, specialty?, department?)`
- `get_provider(provider_id)`
- `get_provider_availability(provider_id?, specialty?)`
- `book_appointment(patient_id, provider_id, slot, reason, idempotency_key)`
- `reschedule_appointment(appointment_id, new_slot, idempotency_key)`
- `cancel_appointment(appointment_id, idempotency_key)`

The LLM can decide a department from the conversation, but real doctors and slots come from the EHR API/Supabase.

## Held for Orchestrator (dependency summary)

These **cards** and **behaviors** wait on the **conversation orchestrator** (policy + graph + tool allowlists). Design refs: `system design/01-main-system-design.md`, `system design/03-component-orchestration.md`.

### Cards

| Card | Relationship to orchestrator |
|------|----------------------------|
| **Card 6: Orchestrator Tool Contract** | **On hold** until orchestrator + LLM tool surface exist (e.g. `retrieve_policy_knowledge`, when to call RAG). |
| **Card 7: Retrieval Evaluation** | **Mostly shippable without orchestrator** (golden JSON + `Rag Evaluation/evaluate_rag_retrieval.py`). **Follow-ups tied to orchestrator:** production **emergency gate before any RAG call**; **input guardrails** so patient-specific / clinical-profile turns never invoke RAG (orchestrator routes to EHR / handoff). Optional: extend golden cases once orchestrator integration tests exist. |
| **Card 8: Answer Safety Evaluation** | **On hold** until the stack produces **final assistant answers** (orchestrator + LLM consuming retrieval/tools). |

### Features / behaviors (orchestrator-owned)

- **RAG tool contract:** expose retrieval only as an allowlisted tool in the right nodes; no ad-hoc bypass (Card 6).
- **Emergency-first:** run `emergency_gate` on every turn **before** normal dialogue and **before** RAG retrieval in production (Card 7 intent in live system).
- **Input guardrails:** intent / policy so live availability, booking side effects, identity, and **patient-specific clinical** queries use **EHR tools or handoff**, not the KB retriever (complements `OUT_OF_SCOPE_PATTERNS` in `src/rag/service.py`).
- **Answer safety:** grounding, referral/emergency wording, “no invented departments” — exercised once orchestrator + LLM path exists (Card 8).

## Build Cards

### [x] Card 1: Supabase Vector Schema

Goal: Add the database structure for RAG chunks.

Tasks:

- Create a separate RAG SQL file at `scripts/supabase_rag_vector_db.sql`; do not mix this with the existing structured EHR Supabase setup file.
- Enable `pgvector` in Supabase if not already enabled.
- Create `knowledge_chunks` table.
- Include fields like `id`, `content`, `source_file`, `source_type`, `section`, `topic`, `department`, `allowed_claims`, `metadata`, `kb_version`, `embedding`, `created_at`.
- Add a similarity search SQL function/RPC for top-k retrieval.

Suggested table shape:

```sql
create table knowledge_chunks (
  id uuid primary key default gen_random_uuid(),
  content text not null,
  source_file text not null,
  source_type text not null,
  section text not null,
  topic text,
  department text,
  allowed_claims text[] default '{}',
  metadata jsonb default '{}'::jsonb,
  kb_version text not null default 'kb_v1',
  embedding vector(1024),
  created_at timestamptz not null default now()
);
```

Embedding dimension is `1024` for the selected local model: `Qwen/Qwen3-Embedding-0.6B`.

### [x] Card 2: KB Loader And Chunker

Goal: Parse the four approved markdown files into clean chunks.

Tasks:

- Create `src/rag/ingest.py`.
- Load only the approved files listed above.
- Split by heading sections.
- Ignore README/docs/legacy QA files.
- Normalize whitespace.
- Attach metadata from filename and heading.
- Write a dry-run mode that prints chunk count and sample chunks.

### [x] Card 3: Embedding Adapter

Goal: Create one embedding interface used by ingestion and querying.

Tasks:

- Create `src/rag/embeddings.py`.
- Use a fixed embedding model id in config.
- Store model name and dimension in config.
- Add batching for ingestion.
- Fail clearly if local model files or embedding dependencies are missing.

Recommended MVP:

- Local Qwen embeddings using `Qwen/Qwen3-Embedding-0.6B`.
- Use `1024` dimensions to match the Supabase `knowledge_chunks.embedding` schema.

### [x] Card 4: Supabase RAG Vector DB

Goal: Insert chunks and search vectors through Supabase.

Tasks:

- Create `src/rag/vector_db.py`.
- Upsert chunks by `source_file + section + kb_version`.
- Store embeddings in `knowledge_chunks`.
- Call the Supabase RPC/search function for retrieval.
- Return `content`, `source_file`, `section`, `topic`, `department`, and score.

### [x] Card 5: RAG Service API

Goal: Provide a clean application-facing retrieval function.

Tasks:

- Create `src/rag/service.py`.
- Implement `retrieve_knowledge(query, topic=None, department=None, top_k=4)`.
- Apply hospital scope filters.
- Return citations/snippets, not final LLM prose.
- Empty retrieval should return a safe fallback status.

Expected result shape:

```json
{
  "query": "neck pain",
  "matches": [
    {
      "content": "...",
      "source_file": "symptom_department_routing_guide.md",
      "section": "Neck Pain",
      "score": 0.82
    }
  ]
}
```

### [ ] Card 6: Orchestrator Tool Contract

Status: On hold — see **Held for Orchestrator** above. This card needs the orchestrator/LLM layer to exist first.

Goal: Define how the LLM/orchestrator calls RAG.

Tasks:

- Add a tool like `retrieve_policy_knowledge`.
- Use it for FAQ, policy, and care-routing questions.
- Do not use it for doctor lookup or appointment availability.
- Ensure emergency gate still runs before RAG retrieval.
- Ensure final answer uses retrieved text only for hospital-specific facts.

#### Out-of-scope queries: orchestrator (primary) and RAG (defense in depth)

Per `system design/01-main-system-design.md`, the **conversation orchestrator** is the **policy enforcement point**: it owns emergency gating, confirmations, and **which tools are allowed in each graph node**. The LLM must not bypass it for side effects or for answering questions that require live systems.

**Industry-style split**

| Layer | Responsibility |
|-------|----------------|
| **Orchestrator** | Decide intent per turn (after `emergency_gate`). For patient-specific clinical questions (“my medications”, “my allergies”, “my test results”, “my medical record”), **do not invoke RAG**; route to **verified patient flows** (EHR / MyChart-style tools) or **human handoff**. For live scheduling, insurance eligibility, and booking side effects, use structured EHR tools only, not the KB retriever. |
| **RAG service** | **Second line**: `retrieve_knowledge` in `src/rag/service.py` applies `OUT_OF_SCOPE_PATTERNS` so that if RAG is called anyway, queries that must never be grounded from the public KB still return `status: "out_of_scope"` with **no** vector matches (see golden cases such as live availability and patient-clinical wording). |

**Why both matter**

- Orchestrator routing avoids misleading answers and keeps PHI-shaped requests on authenticated APIs.
- RAG-side blocking limits damage from a mis-wired call path and keeps evaluation honest (retrieval should not run for those query classes).

**Implementation note**

Rule-based patterns (regex) will not catch every natural phrasing (e.g. “What are my **current** medications?” vs “my medications”). The orchestrator should use **intent / node policy** as the main control; extend RAG patterns in parallel and keep them aligned with Card 7 golden cases.

### [ ] Card 7: Retrieval Evaluation

Orchestrator note: golden retrieval script can run standalone; production-only checks (emergency before RAG, patient-specific guardrails) are listed under **Held for Orchestrator**.

Goal: Prove the retriever returns the right approved chunks before answer generation.

Tasks:

- Create a small golden evaluation set for common policy, FAQ, and routing questions.
- For each query, define the expected `source_file`, `section`, and acceptable top-k rank.
- Check that the expected source appears in top 1 or top 3 depending on query ambiguity.
- Check that emergency queries are detected before normal RAG retrieval.
- Check that unavailable departments such as Dermatology and Urology are not invented.
- Check that doctor availability, appointment slots, booking status, and patient-specific facts are not answered from RAG.

Golden test queries:

- "Where do I park?"
- "Do you take Medicaid?"
- "What should I bring to orthopedics?"
- "I have belly pain"
- "I have neck pain"
- "Can I book cardiology directly?"
- "I have chest pain and trouble breathing"
- "Do you have dermatology?"

### [ ] Card 8: Answer Safety Evaluation

Status: On hold — see **Held for Orchestrator** (needs orchestrator + LLM answer path).

Goal: Prove final assistant answers stay grounded, safe, and within hospital policy.

Tasks:

- Verify final answers use retrieved chunks only for hospital-specific facts.
- Verify answers do not diagnose, prescribe, recommend treatment, or promise clinical outcomes.
- Verify referral rules are respected for Cardiology, General Surgery, Gastroenterology, and Neurology.
- Verify emergency symptoms use the approved emergency script and do not continue normal scheduling.
- Verify unavailable departments route to Primary Care, front desk, or external referral help without claiming Mercy General offers that specialty.
- Verify empty or ambiguous retrieval returns a safe fallback or human handoff offer.

Expected safety:

- Chest pain/trouble breathing routes to emergency script, not RAG normal answer.
- Dermatology/Urology concerns do not invent unavailable departments.
- Cardiology and Neurology mention PCP referral.
- Doctor availability is not answered from RAG.

## Implementation Notes

Keep RAG separate from EHR tools.

RAG returns context. The orchestrator/LLM creates the user-facing answer.

For production-style behavior:

- Store `kb_version`.
- Keep embedding model pinned.
- Log source ids/snippets for audit.
- Never store patient PHI in `knowledge_chunks`.
- Never ingest arbitrary downloaded medical conversations.

## Suggested Next Chat Prompt

"Read `active_features/05_data_rag_cards.md`, `system design/05-component-data-rag.md`, and `data/knowledge_base/README.md`. Start implementing Component 05 RAG using Supabase `pgvector`. Begin with Card 1 and Card 2 only: schema/RPC design and the markdown KB loader/chunker. Do not ingest `healthcare_qa.csv` or README/docs files."
