import os
import json
import glob
from pathlib import Path
from datetime import date
from dateutil.relativedelta import relativedelta
from dateutil.parser import parse as parse_date
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or SUPABASE_URL == "YOUR_SUPABASE_URL_HERE":
    print("Error: Please set your SUPABASE_URL in the .env file.")
    exit(1)

if not SUPABASE_KEY:
    print("Error: Please set your SUPABASE_KEY in the .env file.")
    exit(1)

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

DATA_DIR = Path("data/processed")

# ============================================================
# DOCTOR METADATA LOOKUP
# Mercy General hospital-specific info from docs/doctors.md.
# Keyed by "FirstName LastName" to handle doctors with the
# same last name (e.g., William Thorne vs. Marcus Thorne).
# ============================================================
DOCTOR_METADATA = {
    "Alan Peterson":      {"focus": "Preventative care, chronic disease management", "experience_years": 15, "room": "Room 101", "extension": "Ext. 201", "booking_status": "Accepting new patients"},
    "Sarah Jenkins":      {"focus": "Women's health and preventative screening", "experience_years": 8, "room": "Room 102", "extension": "Ext. 202", "booking_status": "Accepting new patients"},
    "Robert Chen":        {"focus": "Adult complex chronic illness (Hypertension, Diabetes)", "experience_years": 20, "room": "Room 103", "extension": "Ext. 203", "booking_status": "Waitlist (3 weeks)"},
    "Emily Davis":        {"focus": "Geriatric care (Elderly patients)", "experience_years": 12, "room": "Room 104", "extension": "Ext. 204", "booking_status": "Accepting new patients"},
    "William Thorne":     {"focus": "Sports physicals and joint health", "experience_years": 5, "room": "Room 105", "extension": "Ext. 205", "booking_status": "Accepting new patients"},
    "Maria Garcia":       {"focus": "General practice and pediatric crossover", "experience_years": 10, "room": "Room 106", "extension": "Ext. 206", "booking_status": "Accepting new patients"},
    "David Kim":          {"focus": "Cardiac emergencies and trauma resuscitation", "experience_years": 14, "room": "ER Bay A", "extension": "Ext. 911", "booking_status": "ER Walk-ins only"},
    "Samantha Wright":    {"focus": "Acute respiratory distress and asthma attacks", "experience_years": 9, "room": "ER Bay B", "extension": "Ext. 912", "booking_status": "ER Walk-ins only"},
    "Charles Brooks":     {"focus": "Orthopedic trauma and fracture stabilization", "experience_years": 6, "room": "ER Bay C", "extension": "Ext. 913", "booking_status": "ER Walk-ins only"},
    "Olivia Patel":       {"focus": "Toxicology and severe allergic reactions", "experience_years": 11, "room": "ER Bay D", "extension": "Ext. 914", "booking_status": "ER Walk-ins only"},
    "Michael Rossi":      {"focus": "Newborn care and early childhood development", "experience_years": 18, "room": "Room 201", "extension": "Ext. 301", "booking_status": "Requires vaccination records prior to first visit"},
    "Rachel Greene":      {"focus": "Adolescent medicine and teenage mental health", "experience_years": 7, "room": "Room 202", "extension": "Ext. 302", "booking_status": "Accepting new patients"},
    "James Miller":       {"focus": "Pediatric asthma and allergies", "experience_years": 12, "room": "Room 203", "extension": "Ext. 303", "booking_status": "Accepting new patients"},
    "Sophia Carter":      {"focus": "High-risk obstetrics and complex pregnancies", "experience_years": 16, "room": "Room 301", "extension": "Ext. 401", "booking_status": "Referral required for high-risk patients"},
    "Angela Davis":       {"focus": "General gynecology and menopause management", "experience_years": 22, "room": "Room 302", "extension": "Ext. 402", "booking_status": "Accepting new patients"},
    "Priya Sharma":       {"focus": "Infertility and family planning", "experience_years": 9, "room": "Room 303", "extension": "Ext. 403", "booking_status": "Accepting new patients"},
    "Elena Rostova":      {"focus": "Interventional cardiology (stents, angioplasty)", "experience_years": 25, "room": "Heart Institute Suite A", "extension": "Ext. 501", "booking_status": "PCP Referral required"},
    "Marcus Thorne":      {"focus": "Electrophysiology and heart arrhythmias", "experience_years": 14, "room": "Heart Institute Suite B", "extension": "Ext. 502", "booking_status": "PCP Referral required"},
    "James Lin":          {"focus": "Total joint replacement (knee and hip)", "experience_years": 19, "room": "Ortho Wing Room 1", "extension": "Ext. 601", "booking_status": "Must bring recent X-Rays/MRIs to visit"},
    "Rebecca Vance":      {"focus": "Sports injuries and arthroscopic surgery", "experience_years": 11, "room": "Ortho Wing Room 2", "extension": "Ext. 602", "booking_status": "Accepting new patients"},
    "Thomas Rivera":      {"focus": "Laparoscopic and minimally invasive surgery", "experience_years": 21, "room": "Surgery Center", "extension": "Ext. 701", "booking_status": "Consultations by referral only"},
    "Jessica Moore":      {"focus": "Hernia repair and trauma surgery", "experience_years": 8, "room": "Surgery Center", "extension": "Ext. 702", "booking_status": "Consultations by referral only"},
    "Daniel Lee":         {"focus": "Digestive system, ulcers, and colonoscopies", "experience_years": 17, "room": "Room 401", "extension": "Ext. 801", "booking_status": "Accepting new patients"},
    "Christopher Nolan":  {"focus": "Nervous system, brain disorders, stroke recovery, and severe migraines", "experience_years": 13, "room": "Room 402", "extension": "Ext. 802", "booking_status": "PCP Referral required"},
    "Lisa Wong":          {"focus": "Mental health, behavioral disorders, and medication management", "experience_years": 10, "room": "Room 403", "extension": "Ext. 803", "booking_status": "Accepting new patients"},
}


# ============================================================
# DOCTOR MIGRATION
# ============================================================
def migrate_doctors():
    print("=" * 50)
    print("Migrating Doctors...")
    print("=" * 50)
    doctor_files = glob.glob(str(DATA_DIR / "doctors" / "*.json"))

    success_count = 0
    error_count = 0

    for file_path in doctor_files:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        doc_id = data.get("id")
        npi = next((i.get("value") for i in data.get("identifier", []) if i.get("system") == "http://hl7.org/fhir/sid/us-npi"), "Unknown")

        name_data = data.get("name", [{}])[0]
        first_name = name_data.get("given", [""])[0] if name_data.get("given") else ""
        last_name = name_data.get("family", "")
        prefix = name_data.get("prefix", [""])[0] if name_data.get("prefix") else ""

        telecom = data.get("telecom", [])
        email = next((t.get("value") for t in telecom if t.get("system") == "email"), None)
        phone = next((t.get("value") for t in telecom if t.get("system") == "phone"), None)

        specialty = "General"
        for ext in data.get("extension", []):
            if ext.get("url") == "http://hospital.org/fhir/StructureDefinition/specialty":
                specialty = ext.get("valueString")
                break

        gender = data.get("gender")
        active = data.get("active", True)

        # Look up hospital-specific metadata
        full_name = f"{first_name} {last_name}"
        hospital_meta = DOCTOR_METADATA.get(full_name, {})
        if not hospital_meta:
            print(f"  [WARN] No hospital metadata found for: {full_name}")

        record = {
            "id": doc_id,
            "npi": npi,
            "first_name": first_name,
            "last_name": last_name,
            "prefix": prefix,
            "specialty": specialty,
            "email": email,
            "phone": phone,
            "gender": gender,
            "active": active,
            # Hospital-specific metadata
            "focus": hospital_meta.get("focus"),
            "experience_years": hospital_meta.get("experience_years"),
            "room": hospital_meta.get("room"),
            "extension": hospital_meta.get("extension"),
            "booking_status": hospital_meta.get("booking_status"),
            # Complete raw FHIR JSON
            "raw_fhir_data": data,
        }

        try:
            supabase.table("doctors").upsert(record).execute()
            print(f"  ✓ {prefix} {first_name} {last_name} ({specialty}) — {hospital_meta.get('booking_status', 'N/A')}")
            success_count += 1
        except Exception as e:
            print(f"  ✗ Error inserting doctor {doc_id}: {e}")
            error_count += 1

    print(f"\n  Doctors: {success_count} succeeded, {error_count} failed.\n")


# ============================================================
# PATIENT BUNDLE PARSER
# Extracts the full rich profile per patient_profile_template.md
# ============================================================
def calculate_age(dob_str: str) -> int:
    """Calculate age from a date-of-birth string."""
    try:
        dob = parse_date(dob_str).date()
        return relativedelta(date.today(), dob).years
    except Exception:
        return None


def parse_patient_bundle(bundle_data: dict):
    """
    Parse a full FHIR patient bundle and extract a rich, token-efficient
    clinical profile matching patient_profile_template.md.
    """
    patient_resource = None

    # Intermediate collections
    conditions = []
    medications = []
    encounters = []
    procedures = []
    immunizations = []
    care_plans = []
    allergies = []
    insurance_providers = set()

    # Vitals (we want the most recent reading of each type)
    vitals_raw = {}
    labs_raw = []

    for entry in bundle_data.get("entry", []):
        res = entry.get("resource", {})
        rtype = res.get("resourceType")

        # ── Patient ──────────────────────────────────────────
        if rtype == "Patient":
            patient_resource = res

        # ── Conditions ───────────────────────────────────────
        elif rtype == "Condition":
            status_code = res.get("clinicalStatus", {}).get("coding", [{}])[0].get("code", "")
            if status_code == "active":
                onset = res.get("onsetDateTime", res.get("recordedDate", ""))[:10] if res.get("onsetDateTime") or res.get("recordedDate") else None
                conditions.append({
                    "condition": res.get("code", {}).get("text", "Unknown"),
                    "onset_date": onset,
                })

        # ── Medications ──────────────────────────────────────
        elif rtype == "MedicationRequest":
            if res.get("status") == "active":
                authored = res.get("authoredOn", "")[:10] if res.get("authoredOn") else None
                medications.append({
                    "medication": res.get("medicationCodeableConcept", {}).get("text", "Unknown"),
                    "prescribed_on": authored,
                })

        # ── Encounters ───────────────────────────────────────
        elif rtype == "Encounter":
            date_start = (res.get("period", {}).get("start") or "")[:10]
            etype = res.get("type", [{}])[0].get("text", "Encounter")
            # Get reason code text if available
            reason = None
            if res.get("reasonCode"):
                reason = res["reasonCode"][0].get("coding", [{}])[0].get("display")
            encounters.append({
                "date": date_start,
                "type": etype,
                "reason": reason,
            })

        # ── Procedures ───────────────────────────────────────
        elif rtype == "Procedure":
            performed = res.get("performedPeriod", {}).get("start") or res.get("performedDateTime", "")
            procedures.append({
                "procedure": res.get("code", {}).get("text", "Unknown Procedure"),
                "date": performed[:10] if performed else None,
            })

        # ── Immunizations ────────────────────────────────────
        elif rtype == "Immunization":
            if res.get("status") == "completed":
                immunizations.append({
                    "vaccine": res.get("vaccineCode", {}).get("text", "Unknown Vaccine"),
                    "date": (res.get("occurrenceDateTime") or "")[:10],
                })

        # ── Care Plans ───────────────────────────────────────
        elif rtype == "CarePlan":
            for activity in res.get("activity", []):
                plan_text = activity.get("detail", {}).get("code", {}).get("text")
                plan_status = activity.get("detail", {}).get("status", "unknown")
                if plan_text:
                    care_plans.append({"plan": plan_text, "status": plan_status})

        # ── Allergies ────────────────────────────────────────
        elif rtype == "AllergyIntolerance":
            clinical_status = res.get("clinicalStatus", {}).get("coding", [{}])[0].get("code", "")
            if clinical_status == "active":
                allergies.append({
                    "allergy": res.get("code", {}).get("text", "Unknown Allergy"),
                    "criticality": res.get("criticality", "unknown"),
                })

        # ── Observations (Vitals & Labs) ─────────────────────
        elif rtype == "Observation":
            category_code = res.get("category", [{}])[0].get("coding", [{}])[0].get("code", "")
            effective_dt = res.get("effectiveDateTime", "")
            code_text = res.get("code", {}).get("text", "")
            value_qty = res.get("valueQuantity", {})
            value_code = res.get("valueCodeableConcept", {}).get("text")

            if category_code == "vital-signs":
                # Store the observation keyed by type; we'll pick the latest later
                entry_data = {
                    "date": effective_dt[:10] if effective_dt else "",
                    "value_qty": value_qty,
                    "value_code": value_code,
                    "components": res.get("component", []),
                }
                # Keep only the most recent per vital type
                existing = vitals_raw.get(code_text)
                if not existing or effective_dt > existing["date"]:
                    vitals_raw[code_text] = entry_data

            elif category_code == "laboratory":
                if value_qty.get("value") is not None:
                    labs_raw.append({
                        "test": code_text,
                        "value": f"{value_qty.get('value')} {value_qty.get('unit', '')}".strip(),
                        "date": effective_dt[:10] if effective_dt else "",
                    })

        # ── Insurance (from ExplanationOfBenefit contained Coverage) ─
        elif rtype == "ExplanationOfBenefit":
            for contained in res.get("contained", []):
                if contained.get("resourceType") == "Coverage":
                    payer = contained.get("type", {}).get("text")
                    if payer and payer != "NO_INSURANCE":
                        insurance_providers.add(payer)

    if not patient_resource:
        return None, {}

    # ── Build Patient Info ───────────────────────────────────
    dob = patient_resource.get("birthDate")
    name_data = patient_resource.get("name", [{}])[0]
    first_name = name_data.get("given", [""])[0] if name_data.get("given") else ""
    last_name = name_data.get("family", "")
    patient_info = {
        "name": f"{first_name} {last_name}".strip(),
        "age": calculate_age(dob) if dob else None,
        "gender": patient_resource.get("gender"),
        "phone": next((t.get("value") for t in patient_resource.get("telecom", []) if t.get("system") == "phone"), None),
    }

    # ── Build Vitals ─────────────────────────────────────────
    def get_vital(key_fragment):
        """Find a vital by partial key match."""
        for k, v in vitals_raw.items():
            if key_fragment.lower() in k.lower():
                return v
        return None

    height_v = get_vital("Height")
    weight_v = get_vital("Weight")
    bmi_v = get_vital("Mass Index")
    bp_v = get_vital("Blood Pressure")
    smoking_v = get_vital("Tobacco")
    pain_v = get_vital("Pain severity")

    def fmt_qty(v):
        if v and v.get("value_qty"):
            return f"{round(v['value_qty'].get('value', 0), 2)} {v['value_qty'].get('unit', '')}".strip()
        return None

    # Blood pressure is a component observation
    bp_str = None
    if bp_v and bp_v.get("components"):
        systolic = next((c.get("valueQuantity", {}).get("value") for c in bp_v["components"]
                         if "Systolic" in c.get("code", {}).get("text", "")), None)
        diastolic = next((c.get("valueQuantity", {}).get("value") for c in bp_v["components"]
                          if "Diastolic" in c.get("code", {}).get("text", "")), None)
        if systolic and diastolic:
            bp_str = f"{round(systolic)}/{round(diastolic)} mmHg"

    recent_vitals = {
        "height": fmt_qty(height_v),
        "weight": fmt_qty(weight_v),
        "bmi": fmt_qty(bmi_v),
        "blood_pressure": bp_str,
        "smoking_status": smoking_v["value_code"] if smoking_v else None,
        "pain_severity": f"{round(pain_v['value_qty'].get('value', 0), 1)}/10" if pain_v and pain_v.get("value_qty") else None,
    }
    # Remove None values
    recent_vitals = {k: v for k, v in recent_vitals.items() if v is not None}

    # ── Sort and Trim Collections ─────────────────────────────
    encounters.sort(key=lambda x: x.get("date") or "", reverse=True)
    recent_visits = encounters[:5]

    # Limit procedures to 10 most recent (prevents LLM context flooding)
    procedures.sort(key=lambda x: x.get("date") or "", reverse=True)
    procedures = procedures[:10]

    # De-duplicate immunizations: keep only the most recent date per vaccine name
    immunizations.sort(key=lambda x: x.get("date") or "", reverse=True)
    seen_vaccines = set()
    unique_immunizations = []
    for imm in immunizations:
        if imm["vaccine"] not in seen_vaccines:
            unique_immunizations.append(imm)
            seen_vaccines.add(imm["vaccine"])
    immunizations = unique_immunizations

    labs_raw.sort(key=lambda x: x.get("date") or "", reverse=True)
    # Keep only the most recent unique test names
    seen_labs = set()
    recent_labs = []
    for lab in labs_raw:
        if lab["test"] not in seen_labs:
            recent_labs.append(lab)
            seen_labs.add(lab["test"])

    # De-duplicate care plans
    seen_plans = set()
    unique_care_plans = []
    for cp in care_plans:
        key = cp["plan"]
        if key not in seen_plans:
            unique_care_plans.append(cp)
            seen_plans.add(key)

    # ── Assemble Final Profile ────────────────────────────────
    clinical_data = {
        "patient_info": patient_info,
        "recent_vitals": recent_vitals,
        "recent_lab_results": recent_labs,
        "active_conditions": conditions,
        "current_medications": medications,
        "procedures": procedures,
        "immunizations": immunizations,
        "ongoing_care_plans": unique_care_plans,
        "recent_visits": recent_visits,
        "allergies": allergies,
        "insurance": sorted(list(insurance_providers)),
    }

    return patient_resource, clinical_data


# ============================================================
# PATIENT MIGRATION
# ============================================================
def migrate_patients():
    print("=" * 50)
    print("Migrating Patients...")
    print("=" * 50)
    patient_files = glob.glob(str(DATA_DIR / "patients" / "*.json"))

    total = len(patient_files)
    success_count = 0
    error_count = 0

    for i, file_path in enumerate(patient_files, 1):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        patient_res, clinical_data = parse_patient_bundle(data)

        if not patient_res:
            print(f"  [SKIP] No Patient resource in: {file_path}")
            continue

        pat_id = patient_res.get("id")

        # Extract MRN
        mrn = pat_id
        for ident in patient_res.get("identifier", []):
            if ident.get("type", {}).get("text") == "Medical Record Number":
                mrn = ident.get("value")
                break

        # Demographics
        name_data = patient_res.get("name", [{}])[0]
        first_name = name_data.get("given", [""])[0] if name_data.get("given") else ""
        last_name = name_data.get("family", "")
        dob = patient_res.get("birthDate")
        gender = patient_res.get("gender")
        phone = next((t.get("value") for t in patient_res.get("telecom", []) if t.get("system") == "phone"), "555-000-0000")
        addr = patient_res.get("address", [{}])[0]
        address_line = addr.get("line", [""])[0] if addr.get("line") else None
        city = addr.get("city")
        state = addr.get("state")
        postal_code = addr.get("postalCode")

        pat_record = {
            "id": pat_id,
            "mrn": mrn,
            "first_name": first_name,
            "last_name": last_name,
            "dob": dob,
            "gender": gender,
            "phone": phone,
            "address_line": address_line,
            "city": city,
            "state": state,
            "postal_code": postal_code,
        }

        # Upsert patient demographics
        try:
            supabase.table("patients").upsert(pat_record).execute()
        except Exception as e:
            print(f"  ✗ [{i}/{total}] Error inserting patient {pat_id}: {e}")
            error_count += 1
            continue

        # Upsert rich medical profile
        prof_record = {"patient_id": pat_id, "clinical_data": clinical_data}
        try:
            existing = supabase.table("medical_profiles").select("id").eq("patient_id", pat_id).execute()
            if existing.data:
                prof_record["id"] = existing.data[0]["id"]
            supabase.table("medical_profiles").upsert(prof_record).execute()
            print(f"  ✓ [{i}/{total}] {first_name} {last_name} — "
                  f"{len(clinical_data.get('active_conditions', []))} conditions, "
                  f"{len(clinical_data.get('current_medications', []))} meds, "
                  f"{len(clinical_data.get('allergies', []))} allergies")
            success_count += 1
        except Exception as e:
            print(f"  ✗ [{i}/{total}] Error inserting profile for {pat_id}: {e}")
            error_count += 1

    print(f"\n  Patients: {success_count} succeeded, {error_count} failed.\n")


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("\n🏥 Starting Supabase Migration — Mercy General Hospital\n")
    migrate_doctors()
    migrate_patients()
    print("✅ Migration Complete!")
