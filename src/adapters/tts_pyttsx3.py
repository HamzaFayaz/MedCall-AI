"""Offline TTS via pyttsx3 (Windows SAPI / system voices). For testing playback."""

import asyncio
import os
import tempfile

import av
import pyttsx3

from src.gateway.audio_track import FRAME_BYTES
from src.logger import logger


class Pyttsx3TTSAdapter:
    """Same interface as DeepgramTTSAdapter for drop-in testing."""

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.on_audio_callback = None
        self._text_buffer = ""
        self._cancelled = False
        self._connected = False
    def set_callback(self, callback):
        self.on_audio_callback = callback

    async def connect(self):
        self._connected = True
        logger.info("Offline pyttsx3 TTS ready.")
        return True

    async def ensure_connected(self) -> bool:
        if not self._connected:
            return await self.connect()
        return True

    async def cancel(self):
        self._cancelled = True
        self._text_buffer = ""

    async def send_text(self, text: str):
        self._text_buffer += text

    async def flush(self):
        text = self._text_buffer.strip()
        self._text_buffer = ""
        if not text:
            return

        self._cancelled = False
        loop = asyncio.get_running_loop()
        try:
            pcm = await loop.run_in_executor(None, self._synthesize_pcm, text)
        except Exception as e:
            logger.error(f"pyttsx3 synthesis failed: {e}")
            raise

        if self._cancelled or not pcm or not self.on_audio_callback:
            return

        for offset in range(0, len(pcm), FRAME_BYTES):
            if self._cancelled:
                break
            chunk = pcm[offset : offset + FRAME_BYTES]
            if asyncio.iscoroutinefunction(self.on_audio_callback):
                await self.on_audio_callback(chunk)
            else:
                self.on_audio_callback(chunk)

    def _synthesize_pcm(self, text: str) -> bytes:
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        engine = None
        try:
            engine = pyttsx3.init()
            engine.save_to_file(text, path)
            engine.runAndWait()
            if engine:
                try:
                    engine.stop()
                except Exception:
                    pass

            container = av.open(path)
            resampler = av.AudioResampler(
                format="s16", layout="mono", rate=self.sample_rate
            )
            pcm = bytearray()
            for frame in container.decode(audio=0):
                for out_frame in resampler.resample(frame):
                    pcm.extend(out_frame.to_ndarray().tobytes())
            return bytes(pcm)
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    async def disconnect(self):
        self._connected = False
        logger.info("Offline pyttsx3 TTS stopped.")
