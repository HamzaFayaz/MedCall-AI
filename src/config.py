import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
    # TTS: deepgram (default) | pyttsx3 | offline | local
    TTS_PROVIDER = os.getenv("TTS_PROVIDER", "deepgram")
    STT_ENDPOINTING_MS = int(os.getenv("STT_ENDPOINTING_MS", "700"))
    STT_UTTERANCE_MERGE_MS = int(os.getenv("STT_UTTERANCE_MERGE_MS", "1200"))
    RAG_EMBEDDING_MODEL_ID = os.getenv(
        "RAG_EMBEDDING_MODEL_ID",
        "Qwen/Qwen3-Embedding-0.6B",
    )
    RAG_EMBEDDING_MODEL_PATH = os.getenv(
        "RAG_EMBEDDING_MODEL_PATH",
        "embedding_models/qwen3-embedding-0.6b",
    )
    RAG_EMBEDDING_DIMENSION = int(os.getenv("RAG_EMBEDDING_DIMENSION", "1024"))
    RAG_EMBEDDING_MAX_LENGTH = int(os.getenv("RAG_EMBEDDING_MAX_LENGTH", "8192"))
    RAG_EMBEDDING_BATCH_SIZE = int(os.getenv("RAG_EMBEDDING_BATCH_SIZE", "4"))
    
config = Config()
