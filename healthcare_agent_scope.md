# Healthcare Patient Scheduler & Intake Agent

## Overview
This document outlines the scope and requirements for a production-grade Healthcare Patient Scheduler and Intake Voice Agent. The agent is designed to handle inbound patient calls, automate appointment scheduling, and perform initial medical intake without requiring immediate human intervention.

## Core Objectives
1. **Reduce Front-Desk Load**: Handle the high volume of routine calls for booking, canceling, and rescheduling.
2. **Automated Intake**: Collect preliminary symptoms, duration of illness, and basic patient information before they see the doctor.
3. **Insurance Verification**: Collect and optionally verify basic insurance provider details.

## Technical Requirements
- **Telephony & Speech**: 
  - Vapi (Primary for handling the phone call lifecycle and conversation flow).
  - Deepgram (For highly accurate, low-latency speech-to-text, crucial for understanding medical terms and background noise).
  - WebRTC (Fallback testing environment if traditional phone numbers face regional restrictions).
- **Integrations (Tools/Function Calling)**:
  - Calendar API (e.g., Google Calendar, Cal.com, or direct EHR integration like Epic/Cerner) to check doctor availability and book slots.
  - Database (to log patient intake notes securely).
- **Guardrails**:
  - Strict prompts preventing the AI from diagnosing conditions or giving medical advice.
  - Fallback logic to seamlessly transfer the call to a human receptionist if the patient experiences an emergency or the request is too complex.

## Expected Call Flow
1. **Greeting**: "Hello, you've reached [Clinic Name]. How can I help you today?"
2. **Intent Recognition**: Determine if the user wants to schedule, cancel, or speak to a nurse.
3. **Intake (If Scheduling)**: "I can help with that. Could you briefly describe the reason for your visit?"
4. **Availability Matching**: The agent checks the calendar API and proposes times. "Dr. Smith has an opening tomorrow at 10 AM or 2 PM. Do either of those work?"
5. **Confirmation**: Books the appointment via API, repeats the time back to the patient, and ends the call.
