import os
import requests
import zipfile
import io

def download_synthea_data():
    print("Downloading Synthea FHIR R4 Sample Data...")
    # This is an official sample dataset from Synthea containing realistic fake patients and doctors
    url = "https://synthetichealth.github.io/synthea-sample-data/downloads/synthea_sample_data_fhir_r4_sep2019.zip"
    
    # Create the output directory
    output_dir = "data/fhir"
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        # Extract the zip file in memory and save the JSON files
        print("Extracting files...")
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            z.extractall(output_dir)
            
        # Count the downloaded files
        files = os.listdir(output_dir)
        json_files = [f for f in files if f.endswith('.json')]
        
        print(f"Success! Downloaded and extracted {len(json_files)} FHIR R4 JSON bundles.")
        print(f"Data saved to: {output_dir}")
        
    except Exception as e:
        print(f"Error downloading or extracting data: {e}")

if __name__ == "__main__":
    download_synthea_data()
