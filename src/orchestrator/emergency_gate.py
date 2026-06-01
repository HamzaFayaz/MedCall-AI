import re
from dataclasses import dataclass

from src.logger import logger
from src.orchestrator.emergency_phrases import (
    EMERGENCY_PHRASES,
    WORD_BOUNDARY_PHRASES,
)

EMERGENCY_SCRIPT = (
    "I am an automated assistant and it sounds like you are experiencing a "
    "medical emergency. Please hang up and dial 911 immediately."
)


@dataclass(frozen=True)
class EmergencyCheckResult:
    triggered: bool
    reason_class: str | None = None


def normalize_text(text: str) -> str:
    lowered = text.lower().strip()
    return re.sub(r"\s+", " ", lowered)


def _phrase_matches(normalized: str, phrase: str) -> bool:
    if phrase in WORD_BOUNDARY_PHRASES or " " not in phrase:
        pattern = r"\b" + re.escape(phrase) + r"\b"
        return re.search(pattern, normalized) is not None
    return phrase in normalized


def check_emergency(text: str) -> EmergencyCheckResult:
    """Deterministic keyword gate; bias toward trigger (no past-tense excludes in v1)."""
    normalized = normalize_text(text)
    if not normalized:
        return EmergencyCheckResult(triggered=False)

    for reason_class, phrases in EMERGENCY_PHRASES.items():
        for phrase in phrases:
            if _phrase_matches(normalized, phrase):
                return EmergencyCheckResult(
                    triggered=True,
                    reason_class=reason_class,
                )

    return EmergencyCheckResult(triggered=False)


def log_emergency_triggered(session_id: str, reason_class: str) -> None:
    logger.warning(
        f"emergency_triggered session_id={session_id} reason_class={reason_class}"
    )
