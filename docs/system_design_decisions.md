# System Design Decisions

This document tracks major architectural and design decisions made throughout the development of the Healthcare Patient Scheduler & Intake Voice Agent.

## 1. Data Processing Architecture: Database Migration to Supabase

**Date:** May 4, 2026

**Context:** 
The project originally planned to utilize Synthea-generated FHIR patient bundles (`data/processed/patients/`) directly via an "on-the-fly" API parsing middleware. However, to better simulate a true production environment and demonstrate scalable cloud architecture, we pivoted to using a managed PostgreSQL database.

**Alternatives Considered:**
1. **On-the-fly API Middleware (Local JSON):** Keep raw FHIR files untouched. Build the `ehr_server.py` API to fetch local files, parse them in memory, and return clean profiles.
2. **Cloud Database (Supabase):** Extract the clean clinical data from the raw FHIR files *once* via a migration script, and store the structured data in a cloud-hosted PostgreSQL database (Supabase). The Voice Agent API will then query this database using standard SQL.

**Decision:** 
We chose **Option 2 (Cloud Database via Supabase)**.

**Rationale:**
*   **Production-Grade Architecture:** Real-world enterprise systems (Epic, Cerner) use massive relational databases, not local JSON files. Connecting to a real SQL database mimics this architecture perfectly.
*   **Performance:** Querying indexed SQL tables (e.g., finding available doctors or looking up a patient by phone number) is infinitely faster than iterating through local text files.
*   **New Patient Creation:** Supabase handles `INSERT` operations (for new patient onboarding and appointment scheduling) safely and cleanly, without the risks of race conditions associated with writing to local JSON files.
*   **Hybrid Storage:** We will use standard SQL columns for searchable data (Patient Demographics, Doctor Specialties) and leverage PostgreSQL's `JSONB` columns to efficiently store the nested medical history (conditions, medications) required by the LLM.
