import asyncio
import fractions
import time

import av
import numpy as np
from aiortc import MediaStreamTrack

from src.logger import logger

# 20 ms @ 16 kHz mono s16 — stable WebRTC frame size
SAMPLE_RATE = 16000
FRAME_SAMPLES = 320
FRAME_BYTES = FRAME_SAMPLES * 2
# Wait longer between TTS chunks before inserting silence (jitter buffer)
TTS_INTER_CHUNK_WAIT_S = 0.12
# Keepalive silence when no TTS is active
IDLE_SILENCE_WAIT_S = 0.02


class AgentAudioTrack(MediaStreamTrack):
    kind = "audio"

    def __init__(self):
        super().__init__()
        self.sample_rate = SAMPLE_RATE
        self.time_base = fractions.Fraction(1, self.sample_rate)
        self._timestamp = 0
        self._buffer = bytearray()
        self._last_push_time = 0.0
        self._data_available = asyncio.Event()

    def push_audio(self, audio_bytes: bytes):
        if not audio_bytes:
            return
        if len(audio_bytes) % 2:
            audio_bytes = audio_bytes[:-1]
        self._buffer.extend(audio_bytes)
        self._last_push_time = time.monotonic()
        self._data_available.set()

    def clear_playback(self):
        self._buffer.clear()
        self._last_push_time = 0.0
        self._data_available.set()

    def _wait_timeout_s(self) -> float:
        if self._buffer:
            return TTS_INTER_CHUNK_WAIT_S
        if self._last_push_time and (time.monotonic() - self._last_push_time) < TTS_INTER_CHUNK_WAIT_S:
            return TTS_INTER_CHUNK_WAIT_S
        return IDLE_SILENCE_WAIT_S

    async def _wait_for_data(self):
        if len(self._buffer) >= FRAME_BYTES:
            return
        self._data_available.clear()
        try:
            await asyncio.wait_for(
                self._data_available.wait(),
                timeout=self._wait_timeout_s(),
            )
        except asyncio.TimeoutError:
            pass

    async def recv(self):
        while len(self._buffer) < FRAME_BYTES:
            await self._wait_for_data()
            if len(self._buffer) >= FRAME_BYTES:
                break
            if self._wait_timeout_s() <= IDLE_SILENCE_WAIT_S:
                break

        if len(self._buffer) >= FRAME_BYTES:
            chunk = bytes(self._buffer[:FRAME_BYTES])
            del self._buffer[:FRAME_BYTES]
        elif self._buffer:
            chunk = bytes(self._buffer) + b"\x00" * (FRAME_BYTES - len(self._buffer))
            self._buffer.clear()
        else:
            chunk = b"\x00" * FRAME_BYTES

        audio_array = np.frombuffer(chunk, dtype=np.int16).reshape(1, -1)
        frame = av.AudioFrame.from_ndarray(audio_array, format="s16", layout="mono")
        frame.sample_rate = self.sample_rate
        frame.pts = self._timestamp
        frame.time_base = self.time_base
        self._timestamp += frame.samples
        return frame


async def process_inbound_audio(
    track: MediaStreamTrack,
    stt_adapter,
    on_pcm_frame=None,
):
    """Read browser audio, run VAD per frame, forward to STT."""
    resampler = av.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
    try:
        while True:
            frame = await track.recv()
            if stt_adapter and stt_adapter.connection:
                resampled_frames = resampler.resample(frame)
                for resampled_frame in resampled_frames:
                    audio_bytes = resampled_frame.to_ndarray().tobytes()
                    if on_pcm_frame:
                        on_pcm_frame(audio_bytes)
                    await stt_adapter.send_audio(audio_bytes)
    except Exception as e:
        logger.info(f"Inbound audio stream ended or errored: {e}")
