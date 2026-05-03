import os
import json
import re
from glob import glob

def get_doctor_details():
    # Read doctors.md
    with open("docs/doctors.md", "r", encoding="utf-8") as f:
        content = f.read()
    
    # Regex to parse the markdown list. Example line:
    # 1. **Dr. Alan Peterson, MD** - Family Medicine
    # We want to extract "Dr. Alan Peterson" and "Family Medicine"
    matches = re.findall(r'\d+\.\s+\*\*(Dr\.\s+.*?)(?:,\s+MD|,\s+DO|,\s+MD,\s+FACC)?\*\*\s+-\s+(.*)', content)
    
    doctors = []
    for name, specialty in matches:
        clean_name = name.strip()
        parts = clean_name.replace("Dr. ", "").split(" ")
        given = parts[:-1] if len(parts) > 1 else [parts[0]]
        family = parts[-1] if len(parts) > 1 else ""
        
        doctors.append({
            "full_name": clean_name,
            "prefix": "Dr.",
            "given": given,
            "family": family,
            "specialty": specialty.strip()
        })
    return doctors

def extract_practitioners(doctors):
    input_dir = "data/fhir/fhir"
    output_dir = "data/processed/doctors"
    os.makedirs(output_dir, exist_ok=True)
    
    json_files = glob(os.path.join(input_dir, "*.json"))
    
    extracted_count = 0
    seen_ids = set()
    
    print(f"Parsed {len(doctors)} doctors from docs/doctors.md")
    print("Extracting from FHIR bundles...")
    
    for file_path in json_files:
        if extracted_count >= len(doctors):
            break
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                bundle = json.load(f)
                
            if bundle.get("resourceType") == "Bundle" and "entry" in bundle:
                for entry in bundle["entry"]:
                    resource = entry.get("resource", {})
                    
                    if resource.get("resourceType") == "Practitioner":
                        practitioner_id = resource.get("id")
                        if practitioner_id and practitioner_id not in seen_ids:
                            seen_ids.add(practitioner_id)
                            
                            doc_info = doctors[extracted_count]
                            
                            # Modify the name to match our mock doctor
                            resource["name"] = [{
                                "family": doc_info["family"],
                                "given": doc_info["given"],
                                "prefix": [doc_info["prefix"]]
                            }]
                            
                            # Add specialty information for the API to easily search later
                            resource["extension"] = [{
                                "url": "http://hospital.org/fhir/StructureDefinition/specialty",
                                "valueString": doc_info["specialty"]
                            }]
                            
                            # Create a safe filename (e.g., Dr_Alan_Peterson.json)
                            safe_name = doc_info["full_name"].replace(" ", "_").replace(".", "")
                            out_path = os.path.join(output_dir, f"{safe_name}.json")
                            
                            with open(out_path, "w", encoding="utf-8") as out_f:
                                json.dump(resource, out_f, indent=4)
                                
                            extracted_count += 1
                            if extracted_count >= len(doctors):
                                break
                                
        except Exception as e:
            continue
            
    print(f"Success! Saved {extracted_count} doctor records to {output_dir}/")

if __name__ == "__main__":
    doctors = get_doctor_details()
    if not doctors:
        print("Error: Could not parse any doctors from docs/doctors.md")
    else:
        extract_practitioners(doctors)
