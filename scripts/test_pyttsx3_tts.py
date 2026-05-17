import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.adapters.tts_pyttsx3 import Pyttsx3TTSAdapter


async def main():
    chunks = []
    adapter = Pyttsx3TTSAdapter()
    adapter.set_callback(lambda b: chunks.append(len(b)))
    await adapter.connect()
    await adapter.send_text("Hello, this is offline TTS.")
    await adapter.flush()
    print(f"chunks={len(chunks)} total_bytes={sum(chunks)}")


if __name__ == "__main__":
    asyncio.run(main())
