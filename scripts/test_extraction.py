"""
Local test script — runs the parse_patient_bundle() function on a single patient
file and pretty-prints the resulting clinical_data JSON. No Supabase connection needed.
Run from the project root: python scripts/test_extraction.py
"""
import json
import sys
from pathlib import Path

# Add the scripts directory to the path so we can import from migrate_to_supabase
sys.path.insert(0, str(Path(__file__).parent))

from migrate_to_supabase import parse_patient_bundle

PATIENT_FILE = Path("data/processed/patients/0a2f735c-8fec-4fb6-a1b9-38589d6ef318.json")

if not PATIENT_FILE.exists():
    print(f"ERROR: File not found: {PATIENT_FILE}")
    sys.exit(1)

print(f"Loading: {PATIENT_FILE.name}\n")

with open(PATIENT_FILE, "r", encoding="utf-8") as f:
    bundle = json.load(f)

patient_res, clinical_data = parse_patient_bundle(bundle)

if not patient_res:
    print("ERROR: No Patient resource found in bundle.")
    sys.exit(1)

print("=" * 60)
print("PATIENT RESOURCE — Demographics")
print("=" * 60)
print(f"  ID:     {patient_res.get('id')}")
print(f"  Name:   {patient_res.get('name', [{}])[0].get('given', ['?'])[0]} {patient_res.get('name', [{}])[0].get('family', '?')}")
print(f"  DOB:    {patient_res.get('birthDate')}")
print(f"  Gender: {patient_res.get('gender')}")
print()

print("=" * 60)
print("EXTRACTED clinical_data (follows patient_profile_template.md)")
print("=" * 60)
print(json.dumps(clinical_data, indent=2))

print()
print("=" * 60)
print("SUMMARY")
print("=" * 60)
for key, val in clinical_data.items():
    if isinstance(val, list):
        print(f"  {key}: {len(val)} item(s)")
    elif isinstance(val, dict):
        print(f"  {key}: {len(val)} field(s)")
    else:
        print(f"  {key}: {val}")
