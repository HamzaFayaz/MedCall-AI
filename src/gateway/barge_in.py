"""Card 6 metrics and barge-in policy helpers."""

from dataclasses import dataclass, field


@dataclass
class BargeInMetrics:
    """Per-session counters; logged on session end."""

    barge_in_count: int = 0
    barge_in_vad: int = 0
    barge_in_stt_partial: int = 0
    barge_in_client_hint: int = 0
    speech_started_count: int = 0
    speech_ended_count: int = 0
    ignored_stt_finals: int = 0

    def record_barge_in(self, reason: str) -> None:
        self.barge_in_count += 1
        if reason == "vad":
            self.barge_in_vad += 1
        elif reason == "stt_partial":
            self.barge_in_stt_partial += 1
        elif reason == "client_hint":
            self.barge_in_client_hint += 1

    def summary(self) -> dict:
        return {
            "barge_in_total": self.barge_in_count,
            "barge_in_vad": self.barge_in_vad,
            "barge_in_stt_partial": self.barge_in_stt_partial,
            "barge_in_client_hint": self.barge_in_client_hint,
            "speech_started": self.speech_started_count,
            "speech_ended": self.speech_ended_count,
            "ignored_stt_finals": self.ignored_stt_finals,
        }
