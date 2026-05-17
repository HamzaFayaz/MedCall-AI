"""Default gateway event handler — logs Card 6 lifecycle events."""

import json

from src.logger import logger


async def log_gateway_event(event: dict) -> None:
    event_type = event.get("type", "")
    session_id = event.get("session_id", "")[:8]

    if event_type in {
        "barge_in.detected",
        "speak.cancel",
        "speech_started",
        "speech_ended",
    }:
        logger.info(f"[{session_id}] {event_type}: {json.dumps(event)}")
    elif event_type == "transcript.final":
        logger.info(f"[{session_id}] user: {event.get('text', '')}")
    else:
        logger.debug(f"[{session_id}] {event_type}")
