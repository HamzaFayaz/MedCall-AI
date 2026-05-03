import os
import json
import random
from glob import glob

def load_approved_doctors():
    doc_dir = "data/processed/doctors"
    doctors = {}
    family_docs = []
    
    # Load all 25 doctors we extracted
    for file_path in glob(os.path.join(doc_dir, "*.json")):
        with open(file_path, 'r', encoding='utf-8') as f:
            doc = json.load(f)
            doc_id = doc.get("id")
            
            # Check specialty
            specialty = "Unknown"
            if "extension" in doc:
                specialty = doc["extension"][0]["valueString"]
            
            doctors[doc_id] = doc
            
            # We will use Primary Care doctors for general remapping
            if "Family Medicine" in specialty or "Internal Medicine" in specialty:
                family_docs.append(doc_id)
                
    return doctors, family_docs

def process_patients():
    input_dir = "data/fhir/fhir"
    output_dir = "data/processed/patients"
    os.makedirs(output_dir, exist_ok=True)
    
    approved_doctors, family_docs = load_approved_doctors()
    approved_ids = set(approved_doctors.keys())
    
    json_files = glob(os.path.join(input_dir, "*.json"))
    
    print(f"Loaded {len(approved_ids)} approved doctors.")
    print(f"Processing {len(json_files)} raw patient files...")
    
    processed_count = 0
    remapped_encounters = 0
    
    for file_path in json_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                bundle = json.load(f)
                
            if bundle.get("resourceType") != "Bundle" or "entry" not in bundle:
                continue
                
            patient_resource = None
            clean_entries = []
            
            # Step 1: Keep patient data, drop unapproved doctors
            for entry in bundle["entry"]:
                resource = entry.get("resource", {})
                rtype = resource.get("resourceType")
                
                if rtype == "Patient":
                    patient_resource = resource
                    clean_entries.append(entry)
                elif rtype == "Practitioner":
                    # Only keep the practitioner inside the bundle if it's one of our 25
                    if resource.get("id") in approved_ids:
                        clean_entries.append(entry)
                else:
                    # Keep Encounters, Conditions, Medications, etc.
                    clean_entries.append(entry)
                    
            if not patient_resource:
                continue
                
            patient_id = patient_resource.get("id")
            
            # Step 2: Remap past Encounters to our doctors
            for entry in clean_entries:
                resource = entry.get("resource", {})
                if resource.get("resourceType") == "Encounter":
                    if "participant" in resource:
                        for p in resource["participant"]:
                            if "individual" in p and "reference" in p["individual"]:
                                ref = p["individual"]["reference"]
                                # Extract UUID from urn:uuid:xxx
                                ref_id = ref.split(":")[-1] if ":" in ref else ref
                                
                                # If the doctor who treated them is NOT in our 25 list
                                if ref_id not in approved_ids:
                                    # Remap them to one of our Primary Care doctors
                                    new_doc_id = random.choice(family_docs)
                                    p["individual"]["reference"] = f"urn:uuid:{new_doc_id}"
                                    remapped_encounters += 1
            
            # Create a clean bundle for this patient
            clean_bundle = {
                "resourceType": "Bundle",
                "type": "collection",
                "entry": clean_entries
            }
            
            # Save the patient to the processed folder
            out_path = os.path.join(output_dir, f"{patient_id}.json")
            with open(out_path, "w", encoding="utf-8") as out_f:
                json.dump(clean_bundle, out_f)
                
            processed_count += 1
            if processed_count % 300 == 0:
                print(f"  ...processed {processed_count} patients")
                
        except Exception as e:
            print(f"Error processing file: {e}")
            
    print("-" * 40)
    print("DATA PROCESSING COMPLETE")
    print(f"Total Patients Extracted: {processed_count}")
    print(f"Total Old Doctor References Remapped: {remapped_encounters}")
    print(f"Saved to: {output_dir}/")

if __name__ == "__main__":
    process_patients()
