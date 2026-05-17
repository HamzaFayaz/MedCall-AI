"""
Card 6 — VAD strategy (documented choice)

Primary:   Gateway RMS on inbound PCM resampled to 16 kHz mono (low latency).
Barge-in:  Same VAD while agent is speaking + Deepgram STT partials as backup.
Optional:  Client WebRTC data-channel speech hints (see client/app.js).

Tuning: set VAD_RMS_THRESHOLD in the environment (default 450).
"""

import os

import numpy as np

SPEECH_RMS_THRESHOLD = int(os.getenv("VAD_RMS_THRESHOLD", "450"))
# ~60 ms speech to mark speech_started
FRAMES_TO_START_SPEECH = 3
# ~300 ms silence to mark speech_ended
FRAMES_TO_END_SPEECH = 15
# ~40 ms voiced audio to trigger barge-in while agent speaks
FRAMES_FOR_BARGE_IN = 2


def frame_rms(pcm_bytes: bytes) -> float:
    if len(pcm_bytes) < 4:
        return 0.0
    samples = np.frombuffer(pcm_bytes, dtype=np.int16)
    return float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))


def is_speech_frame(pcm_bytes: bytes) -> bool:
    return frame_rms(pcm_bytes) >= SPEECH_RMS_THRESHOLD


class GatewayVAD:
    """Tracks user speech boundaries and barge-in frame counts."""

    def __init__(self):
        self.user_speaking = False
        self._speech_frames = 0
        self._silence_frames = 0
        self._barge_frames = 0

    def reset_barge_counter(self):
        self._barge_frames = 0

    def process_frame(
        self,
        pcm_bytes: bytes,
        agent_speaking: bool,
    ) -> tuple[bool, bool, bool]:
        """
        Returns (speech_started, speech_ended, barge_in_ready).
        """
        speech_started = False
        speech_ended = False
        barge_in_ready = False
        voiced = is_speech_frame(pcm_bytes)

        if voiced:
            self._speech_frames += 1
            self._silence_frames = 0

            if not self.user_speaking and self._speech_frames >= FRAMES_TO_START_SPEECH:
                self.user_speaking = True
                speech_started = True

            if agent_speaking:
                self._barge_frames += 1
                if self._barge_frames >= FRAMES_FOR_BARGE_IN:
                    barge_in_ready = True
                    self._barge_frames = 0
        else:
            self._speech_frames = 0
            self._silence_frames += 1
            self._barge_frames = 0

            if self.user_speaking and self._silence_frames >= FRAMES_TO_END_SPEECH:
                self.user_speaking = False
                speech_ended = True

        return speech_started, speech_ended, barge_in_ready
