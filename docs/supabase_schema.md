# Supabase Database Schema

To support the AI Voice Agent, we are using a hybrid PostgreSQL + JSONB approach in Supabase. This allows us to use structured relational data for searching and scheduling, while maintaining the flexibility of JSON for complex, nested medical records.

## 1. Doctors Table (`doctors`)
Stores the roster of the 25 authorized doctors at Mercy General. This table is used for routing, cross-coverage logic, and appointment scheduling.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY` | The unique FHIR Practitioner ID. |
| `npi` | `VARCHAR` | `UNIQUE, NOT NULL` | National Provider Identifier. |
| `first_name` | `VARCHAR` | `NOT NULL` | Doctor's first name. |
| `last_name` | `VARCHAR` | `NOT NULL` | Doctor's last name. |
| `prefix` | `VARCHAR` | | e.g., "Dr." |
| `specialty` | `VARCHAR` | `NOT NULL` | Medical department (e.g., "Family Medicine", "Cardiology"). |
| `email` | `VARCHAR` | | Contact email address. |
| `phone` | `VARCHAR` | | Contact phone number. |
| `gender` | `VARCHAR` | | Doctor's gender. |
| `active` | `BOOLEAN` | `DEFAULT TRUE` | Whether the doctor is currently accepting patients. |
| `focus` | `TEXT` | | Clinical focus area (e.g., "Preventative care, chronic disease management"). |
| `experience_years` | `INT` | | Years of medical experience. |
| `room` | `VARCHAR` | | Physical location at Mercy General (e.g., "Room 101", "ER Bay A"). |
| `extension` | `VARCHAR` | | Hospital phone extension (e.g., "Ext. 201"). |
| `booking_status` | `VARCHAR` | | Current availability (e.g., "Accepting new patients", "PCP Referral required"). |
| `raw_fhir_data` | `JSONB` | | The complete, unmodified FHIR Practitioner resource JSON. |

---

## 2. Patients Table (`patients`)
Stores the core demographic information of the patients. This data is used by the Voice Agent to authenticate the caller based on Name, DOB, and Phone number.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY` | The unique FHIR Patient ID. |
| `mrn` | `VARCHAR` | `UNIQUE` | Medical Record Number. |
| `first_name` | `VARCHAR` | `NOT NULL` | Patient's first name. |
| `last_name` | `VARCHAR` | `NOT NULL` | Patient's last name. |
| `dob` | `DATE` | `NOT NULL` | Date of Birth (used for authentication). |
| `gender` | `VARCHAR` | | Patient's gender. |
| `phone` | `VARCHAR` | `NOT NULL` | Phone number (used for caller ID/auth). |
| `address_line`| `VARCHAR` | | Street address. |
| `city` | `VARCHAR` | | City. |
| `state` | `VARCHAR` | | State. |
| `postal_code` | `VARCHAR` | | Zip/Postal Code. |
| `created_at` | `TIMESTAMP` | `DEFAULT NOW()` | Record creation timestamp. |

> **Note on New Patients:** When the agent handles a new patient onboarding call, a "shell" profile will be created in this table with the patient's basic demographic data.

---

## 3. Medical Profiles Table (`medical_profiles`)
Instead of creating dozens of relational tables for every FHIR resource (Conditions, Observations, Medications, etc.), we extract the clinical essence from the raw JSON and store it in a single JSONB column. This is highly optimized for passing context to the LLM.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY` | Unique ID for the profile record. |
| `patient_id` | `UUID` | `FOREIGN KEY (patients.id)` | Link to the specific patient. |
| `clinical_data`| `JSONB` | `NOT NULL` | Rich, structured medical summary following `patient_profile_template.md`. |
| `last_updated` | `TIMESTAMP` | `DEFAULT NOW()` | Last time the profile was synced. |

### Expected `clinical_data` JSONB Structure:
```json
{
  "patient_info": {"name": "Keisha Kris", "age": 34, "gender": "female", "phone": "555-332-5138"},
  "recent_vitals": {
    "height": "166.9 cm", "weight": "60.9 kg", "bmi": "21.8",
    "blood_pressure": "127/78 mmHg", "smoking_status": "Never smoker", "pain_severity": "1.5/10"
  },
  "recent_lab_results": [
    {"test": "Hemoglobin [Mass/volume] in Blood", "value": "12.5 g/dL", "date": "2013-01-21"}
  ],
  "active_conditions": [{"condition": "Normal pregnancy", "onset_date": "2014-11-24"}],
  "current_medications": [{"medication": "Prenatal vitamins", "prescribed_on": "2014-11-24"}],
  "procedures": [{"procedure": "Suture open wound", "date": "2010-11-04"}],
  "immunizations": [{"vaccine": "Influenza, seasonal", "date": "2013-01-21"}],
  "ongoing_care_plans": [{"plan": "Wound care", "status": "completed"}],
  "recent_visits": [{"date": "2014-11-24", "type": "Prenatal initial visit", "reason": "Normal pregnancy"}],
  "allergies": [{"allergy": "Allergy to bee venom", "criticality": "low"}],
  "insurance": ["Cigna Health"]
}
```

---

## 4. Appointments Table (`appointments`)
Tracks all scheduled, completed, and canceled appointments. The Voice Agent will query this table to check for existing appointments or create new ones.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY` | Unique appointment ID. |
| `patient_id` | `UUID` | `FOREIGN KEY (patients.id)` | Patient booking the visit. |
| `doctor_id` | `UUID` | `FOREIGN KEY (doctors.id)` | Doctor providing the care. |
| `appointment_time`| `TIMESTAMP` | `NOT NULL` | Scheduled date and time. |
| `status` | `VARCHAR` | `NOT NULL` | e.g., 'scheduled', 'completed', 'canceled'. |
| `reason` | `TEXT` | | Patient's stated reason for visit. |
| `created_at` | `TIMESTAMP` | `DEFAULT NOW()` | When the appointment was booked. |

## Next Steps for Migration
1. Run **Section 2 (ALTER TABLE)** of `supabase_setup.sql` in the Supabase SQL Editor to add the new columns.
2. Run the updated `migrate_to_supabase.py` script to re-seed all data with rich profiles.
