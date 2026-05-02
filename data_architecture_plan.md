# Data Architecture & Integration Plan

## Overview
This document outlines the production-grade data architecture for the AI Voice Agent. We are moving away from static markdown mock data and building a dynamic, EHR-compliant integration layer using FHIR standards and real-world Medical QA datasets.

## Phase 1: Seed Data Acquisition
We require two types of realistic data to test the agent safely:

1.  **Medical Knowledge Base (Hugging Face)**
    *   **Source:** `adrianf12/healthcare-qa-dataset`
    *   **Format:** JSONL / CSV
    *   **Purpose:** To feed our local Vector Database (ChromaDB) so the agent can accurately answer general medical questions and perform basic triage (e.g., distinguishing between a sprain and a break).

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
    *   Ingests the QA dataset into a local ChromaDB instance.
    *   Provides semantic search so the LLM can pull specific clinic policies and medical answers in milliseconds.
