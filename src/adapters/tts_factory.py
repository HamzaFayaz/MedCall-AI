import os

from src.adapters.tts_deepgram import DeepgramTTSAdapter
from src.adapters.tts_pyttsx3 import Pyttsx3TTSAdapter
from src.logger import logger


def create_tts_adapter(sample_rate: int = 16000):
    provider = os.getenv("TTS_PROVIDER", "deepgram").strip().lower()
    if provider in ("pyttsx3", "offline", "local"):
        logger.info("Using offline TTS (pyttsx3)")
        return Pyttsx3TTSAdapter(sample_rate=sample_rate)
    return DeepgramTTSAdapter(sample_rate=sample_rate)
