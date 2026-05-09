import asyncio
from aiortc import MediaStreamTrack
import av
from src.logger import logger

class AgentAudioTrack(MediaStreamTrack):
    kind = "audio"

    def __init__(self, track: MediaStreamTrack, stt_adapter):
        super().__init__()
        self.track = track
        self.stt_adapter = stt_adapter
        
        # Deepgram requires 16000Hz, Mono, 16-bit PCM
        self._resampler = av.AudioResampler(
            format="s16", layout="mono", rate=16000
        )

    async def recv(self):
        # 1. Receive an audio frame from the browser (Microphone)
        frame = await self.track.recv()
        
        # 2. Resample and send to Deepgram STT
        try:
            if self.stt_adapter and self.stt_adapter.connection:
                resampled_frames = self._resampler.resample(frame)
                for resampled_frame in resampled_frames:
                    # Convert to raw PCM bytes
                    audio_bytes = resampled_frame.to_ndarray().tobytes()
                    # Send to Deepgram asynchronously (fire and forget so we don't block audio)
                    asyncio.create_task(self.stt_adapter.send_audio(audio_bytes))
        except Exception as e:
            logger.error(f"Error processing audio frame: {e}")

        # 3. Output to the browser (Speaker)
        # We don't have Card 4 (TTS) built yet!
        # For now, we will return the incoming frame as an "echo" so you
        # can hear that the WebRTC audio is making the full round-trip.
        return frame
