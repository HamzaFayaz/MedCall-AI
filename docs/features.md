# AI Voice Agent Core Features

This document outlines the six core capabilities of the Healthcare Patient Scheduler & Intake Voice Agent.

## 1. Smart Appointment Scheduling & Management
*   **Booking:** Allowing patients to schedule appointments with specific doctors.
*   **Rescheduling & Canceling:** Handling modifications to existing appointments over the phone.
*   **Cross-Coverage Logic:** If a patient asks for their Primary Care Doctor, but that doctor is fully booked, the agent will automatically search for and offer an alternative doctor within the same department (e.g., another Family Medicine doctor).
*   **ER Routing:** Recognizing that Emergency Room visits don't require scheduled slots and directing patients appropriately.

## 2. Patient Authentication & Profile Fetching
*   **Identity Verification:** Verifying the patient's identity using basic info (e.g., Name, DOB, Phone).
*   **Contextual Awareness:** Pulling their "clean" medical profile from the backend (the `ehr_server.py` API) so the Voice Agent has context about their past conditions, current medications, and recent visits.

## 3. New Patient Onboarding (Shell Profile Creation)
*   **Registration Flow:** Seamlessly transitioning into a new patient flow if the caller is not found in the EHR system.
*   **Shell Profile:** Creating a "shell profile" or basic demographic record rather than collecting full medical history over the phone.
*   **Data Collection:** Asking only for the bare minimum needed to secure the appointment: Full Legal Name, Date of Birth, Phone Number, Gender, and sometimes basic insurance info.
*   **API Integration:** Sending this data to the EHR backend (`POST /api/patients`) to instantly generate a new Patient ID, allowing the agent to book the appointment immediately.

## 4. Conversational Medical Triage (RAG Pipeline)
*   **Knowledge Retrieval:** Listening to the patient's request and using the approved Supabase Vector policy knowledge base files to answer hospital FAQ and route symptoms to the right department safely.
*   **Scope Restriction:** Restricting answers so the AI doesn't promise treatments for conditions the hospital doesn't handle.

## 5. Strict Emergency Guardrails
*   **Keyword Detection:** Continuously listening for critical emergency keywords (e.g., "chest pain," "can't breathe," "severe bleeding").
*   **Immediate Redirection:** Instantly dropping the normal scheduling flow to instruct the patient to hang up and dial 911 or proceed to the nearest ER.

## 6. Basic Intake & Insurance Verification
*   **Symptom Collection:** Collecting preliminary information on how long the patient has been sick or what symptoms they are experiencing.
*   **Billing Context:** Gathering basic insurance provider details to pass along to the billing department.
