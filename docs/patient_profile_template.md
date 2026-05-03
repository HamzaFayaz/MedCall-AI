# Patient Profile Template

This document defines the optimized, token-efficient JSON structure that the `ehr_server.py` API will generate from raw FHIR bundles. This schema contains only the clinically necessary fields required by the AI Voice Agent, filtering out administrative noise and billing data.

## JSON Schema

```json
{
  "patient_info": {
    "name": "Keisha Kris",
    "age": 34,
    "gender": "female",
    "phone": "555-332-5138"
  },
  "recent_vitals": {
    "height": "166.9 cm",
    "weight": "60.9 kg",
    "bmi": "21.8",
    "blood_pressure": "127/78 mmHg",
    "smoking_status": "Never smoker",
    "pain_severity": "1.5/10"
  },
  "recent_lab_results": [
    {"test": "Hemoglobin [Mass/volume] in Blood", "value": "12.5 g/dL", "date": "2013-01-21"},
    {"test": "Leukocytes [#/volume] in Blood", "value": "3.9 10*3/uL", "date": "2013-01-21"},
    {"test": "Platelets [#/volume] in Blood", "value": "218.4 10*3/uL", "date": "2013-01-21"}
  ],
  "active_conditions": [
    {"condition": "Normal pregnancy", "onset_date": "2014-11-24"}
  ],
  "current_medications": [
    {"medication": "Prenatal vitamins", "prescribed_on": "2014-11-24"}
  ],
  "procedures": [
    {"procedure": "Suture open wound", "date": "2010-11-04"},
    {"procedure": "Ultrasound scan for fetal viability", "date": "2014-11-24"}
  ],
  "immunizations": [
    {"vaccine": "Influenza, seasonal", "date": "2013-01-21"},
    {"vaccine": "Hep B, adult", "date": "2013-01-21"}
  ],
  "ongoing_care_plans": [
    {"plan": "Wound care", "status": "completed"}
  ],
  "recent_visits": [
    {"date": "2014-11-24", "type": "Prenatal initial visit", "reason": "Normal pregnancy"}
  ],
  "allergies": []
}
```

## FHIR Mapping Source
- **patient_info**: Extracted from `Patient` resource.
- **recent_vitals**: Extracted from `Observation` resources (category: `vital-signs`). Only the most recent values.
- **recent_lab_results**: Extracted from `Observation` resources (category: `laboratory`). Only the most recent panel.
- **active_conditions**: Extracted from `Condition` resources where `clinicalStatus` is active/resolved.
- **current_medications**: Extracted from `MedicationRequest` resources.
- **procedures**: Extracted from `Procedure` resources.
- **immunizations**: Extracted from `Immunization` resources.
- **ongoing_care_plans**: Extracted from `CarePlan` resources.
- **recent_visits**: Extracted from `Encounter` resources.
- **allergies**: Extracted from `AllergyIntolerance` resources (if present).
