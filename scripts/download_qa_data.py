import os
import pandas as pd
from datasets import load_dataset

def download_healthcare_qa():
    print("Downloading Healthcare QA Dataset from Hugging Face...")
    try:
        # Load the dataset
        # We use a known public dataset for healthcare Q&A
        dataset = load_dataset("adrianf12/healthcare-qa-dataset", split="train")
        
        # Convert to pandas DataFrame for easy inspection and saving
        df = dataset.to_pandas()
        
        # Create data directory if it doesn't exist
        os.makedirs("data", exist_ok=True)
        
        # Save as CSV for local RAG usage
        csv_path = "data/healthcare_qa.csv"
        df.to_csv(csv_path, index=False)
        
        print(f"Success! Downloaded {len(df)} QA pairs.")
        print(f"Saved to: {csv_path}")
        print("\nSample of the data:")
        print(df.head(2))
        
    except Exception as e:
        print(f"Error downloading dataset: {e}")
        print("Please ensure you have installed the required libraries: pip install datasets pandas")

if __name__ == "__main__":
    download_healthcare_qa()
