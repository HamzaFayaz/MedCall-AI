# System Design Decisions

This document tracks major architectural and design decisions made throughout the development of the Healthcare Patient Scheduler & Intake Voice Agent.

## 1. Data Processing Architecture: On-the-fly FHIR Parsing

**Date:** May 3, 2026

**Context:** 
The project utilizes Synthea-generated FHIR patient bundles (`data/processed/patients/`). These raw JSON files are massive (often 10,000+ lines) and contain a significant amount of administrative and billing noise (e.g., `Claim`, `ExplanationOfBenefit`) which would consume excessive tokens and degrade the performance of the AI Voice Agent. The agent requires a clean, concise clinical profile containing only demographics, vitals, active conditions, medications, procedures, immunizations, and recent visits.

**Alternatives Considered:**
1. **Batch Pre-processing:** Run a script to clean all 1,000+ FHIR JSON files upfront and save the "clean" profiles to a new directory on disk.
2. **On-the-fly API Middleware:** Keep the raw FHIR files untouched. Build the `ehr_server.py` API to fetch the raw JSON, apply filtering logic in memory, and return the clean profile dynamically when requested by the Voice Agent.

**Decision:** 
We chose **Option 2 (On-the-fly API Middleware)**.

**Rationale:**
*   **Simulates Enterprise Realities:** Real-world EHR systems (Epic, Cerner) do not allow external agents to copy or permanently alter their raw databases. The Voice Agent must query a secure API middleware layer that fetches and sanitizes data. This architecture perfectly mimics a production environment.
*   **Single Source of Truth & Extensibility:** The raw FHIR bundle remains the untouched source of truth. If the Voice Agent's requirements change in the future (e.g., it suddenly needs to know the patient's `CareTeam` or Primary Care Provider), we only need to update the `ehr_server.py` filtering logic. If we had pre-processed and deleted the raw files, that data would be lost forever, requiring us to re-run the entire data generation pipeline.
*   **Storage Efficiency:** Prevents duplicating thousands of files and maintaining two separate databases on disk.
