import asyncio
from aiortc import MediaStreamTrack
import av
import fractions
import time
import numpy as np
from src.logger import logger

class AgentAudioTrack(MediaStreamTrack):
    kind = "audio"

    def __init__(self):
        super().__init__()
        self.queue = asyncio.Queue()
        # Audio formatting state
        self.sample_rate = 16000
        self.time_base = fractions.Fraction(1, self.sample_rate)
        self._timestamp = 0

    async def recv(self):
        try:
            # Wait for a frame from the TTS queue. If empty, timeout after 20ms.
            # Using wait_for prevents the track from blocking indefinitely,
            # which ensures WebRTC keeps sending packets (even silence) to keep the connection alive.
            audio_bytes = await asyncio.wait_for(self.queue.get(), timeout=0.02)
            
            # Convert raw 16-bit PCM bytes to numpy array
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16).reshape(1, -1)
            frame = av.AudioFrame.from_ndarray(audio_array, format='s16', layout='mono')
            frame.sample_rate = self.sample_rate
            
        except asyncio.TimeoutError:
            # Generate 20ms of silence (320 samples at 16kHz)
            audio_array = np.zeros((1, 320), dtype=np.int16)
            frame = av.AudioFrame.from_ndarray(audio_array, format='s16', layout='mono')
            frame.sample_rate = self.sample_rate

        # Ensure correct timing for WebRTC playback
        frame.pts = self._timestamp
        frame.time_base = self.time_base
        self._timestamp += frame.samples
        
        return frame

async def process_inbound_audio(track: MediaStreamTrack, stt_adapter):
    """Continuously read frames from the browser and send them to STT."""
    resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
    try:
        while True:
            frame = await track.recv()
            if stt_adapter and stt_adapter.connection:
                resampled_frames = resampler.resample(frame)
                for resampled_frame in resampled_frames:
                    # Convert to raw PCM bytes and send to Deepgram
                    audio_bytes = resampled_frame.to_ndarray().tobytes()
                    asyncio.create_task(stt_adapter.send_audio(audio_bytes))
    except Exception as e:
        logger.info(f"Inbound audio stream ended or errored: {e}")
