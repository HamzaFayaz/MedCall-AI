# Data Architecture & Integration Plan

## Overview
This document outlines the production-grade data architecture for the AI Voice Agent. We are moving away from unstructured mock-only data and building a dynamic, EHR-compliant integration layer using FHIR standards plus curated hospital policy knowledge for retrieval.

## Phase 1: Seed Data Acquisition
We require two types of realistic data to test the agent safely:

1.  **Mercy General Policy Knowledge Base**
    *   **Source:** Approved policy files in `data/knowledge_base/`
    *   **Format:** Markdown chunks for Supabase Vector / `pgvector`
    *   **Purpose:** To answer hospital FAQ, referral, insurance, appointment prep, and symptom-to-department routing questions without giving diagnosis or treatment advice.

2.  **Patient & Provider Database (Synthea)**
    *   **Source:** Pre-generated Synthea Ecosystem Bundles
    *   **Format:** FHIR R4 JSON
    *   **Purpose:** To provide a complete, realistic (but fake) hospital ecosystem. Synthea generates BOTH the **Patient Records** (for verification/history) AND the **Provider Directory** (a list of doctors, specialties, and clinics) which the AI will use to search for available appointment slots.

## Phase 2: Mock EHR Integration Layer
The agent will connect to these data sources via a simulated backend.

1.  **`ehr_server.py` (The Hospital API)**
    *   A local FastAPI server acting as a mock Epic EHR.
    *   Exposes endpoints like `/Patient?name=John` and `/Appointment`.
    *   The Voice Agent will be equipped with API tool-calling to ping these endpoints live during the call.

2.  **`rag_pipeline.py` (The Knowledge Retriever)**
    *   Ingests the curated Mercy General policy KB into Supabase Vector / `pgvector`.
    *   Provides semantic search so the LLM can pull specific clinic policies and medical answers in milliseconds.
