import os
import json
from glob import glob

def count_resources(data_dir):
    # Support finding JSONs directly in data_dir or one level deep (like fhir/fhir)
    json_files = glob(os.path.join(data_dir, "*.json")) + glob(os.path.join(data_dir, "*", "*.json"))
    
    unique_patients = set()
    unique_practitioners = set()
    
    print(f"Scanning {len(json_files)} JSON files...")
    
    for file_path in json_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                bundle = json.load(f)
                
            if bundle.get("resourceType") == "Bundle" and "entry" in bundle:
                for entry in bundle["entry"]:
                    resource = entry.get("resource", {})
                    resource_type = resource.get("resourceType")
                    resource_id = resource.get("id")
                    
                    if resource_type == "Patient" and resource_id:
                        unique_patients.add(resource_id)
                    elif resource_type == "Practitioner" and resource_id:
                        unique_practitioners.add(resource_id)
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            
    print("-" * 30)
    print("FHIR Data Count Summary")
    print("-" * 30)
    print(f"Total Unique Patients: {len(unique_patients)}")
    print(f"Total Unique Doctors/Practitioners: {len(unique_practitioners)}")
    print("-" * 30)

if __name__ == "__main__":
    count_resources("data/fhir")
