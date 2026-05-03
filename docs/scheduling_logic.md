# Voice Agent Scheduling & Cross-Coverage Logic

This document defines the production-grade scheduling rules and logic the AI Voice Agent must follow when booking appointments, specifically handling scenarios where a patient's preferred doctor is unavailable.

## 1. Multiple Doctors per Role
To handle high patient volume, Mercy General Hospital employs multiple doctors within the same specialty (e.g., 6 Family Medicine doctors, 4 Emergency Room doctors). The Voice Agent must be aware of the departmental groupings rather than just individual doctor names.

## 2. Cross-Coverage (Partner Coverage) Protocols

In a real hospital, doctors cover for each other. The Voice Agent must implement the following logic based on the department:

### Primary Care (Family & Internal Medicine)
*   **Standard Flow:** Patients usually request their assigned Primary Care Provider (PCP) (e.g., "I need to see Dr. Peterson").
*   **Fallback Logic:** If the requested PCP is fully booked or on leave, the Agent **must not** simply reject the patient. 
*   **Agent Action:** The Agent must query the EHR for *any* available doctor within the same specialty (Family or Internal Medicine) and propose the alternative.
*   *Script Example:* "Dr. Peterson doesn't have any openings today, but his colleague, Dr. Garcia, has an opening at 2:00 PM. Would you like to see her instead?"

### Emergency Room (ER)
*   **Standard Flow:** Patients do not select their ER doctors. 
*   **Agent Action:** If a patient calls regarding an emergency (and it does not require an immediate 911 dispatch), the Agent does not book a specific time slot with a specific doctor. It instructs the patient to proceed to the ER where they will be seen by the attending physician on shift.

### Specialists (Cardiology, Orthopedics, General Surgery, etc.)
*   **Standard Flow:** Patients are referred to a specific specialist and generally stick with them for continuity of care.
*   **Fallback Logic:** Cross-coverage is permitted for urgent issues. If the patient's specific cardiologist is unavailable for an urgent follow-up, the Agent can offer an appointment with another doctor in the same specialist department.
*   *Script Example:* "Dr. Rostova is unavailable this week, but her partner in Cardiology, Dr. Thorne, can see you tomorrow. Would that work?"

## 3. Technical Implementation for the EHR API

To support this logic, the backend `ehr_server.py` must support the following capabilities:
1.  **Search by Name:** `GET /providers?name=Peterson`
2.  **Search by Specialty:** `GET /providers?specialty=Family+Medicine`
3.  **Availability Search by Specialty:** The Voice Agent must be able to ask the API, *"Give me the earliest available slot for ANY doctor in the Family Medicine department."*
