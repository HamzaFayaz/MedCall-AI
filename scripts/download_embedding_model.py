from pathlib import Path

from huggingface_hub import snapshot_download


MODEL_ID = "Qwen/Qwen3-Embedding-0.6B"
OUTPUT_DIR = Path("embedding_models") / "qwen3-embedding-0.6b"


def download_embedding_model() -> None:
    """Download the pinned local embedding model for the RAG layer."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Downloading {MODEL_ID} from Hugging Face...")
    print(f"Saving model files to: {OUTPUT_DIR}")

    snapshot_download(
        repo_id=MODEL_ID,
        local_dir=OUTPUT_DIR,
        local_dir_use_symlinks=False,
    )

    print("Success! Embedding model downloaded.")


if __name__ == "__main__":
    download_embedding_model()
