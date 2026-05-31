import time
from collections import defaultdict
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from aiortc import RTCSessionDescription, RTCConfiguration, RTCIceServer
from src.logger import logger

from src.gateway.events import log_gateway_event
from src.gateway.session import CallSession
from src.orchestrator import clear_session, handle_transcript

webrtc_router = APIRouter(prefix="/webrtc", tags=["WebRTC Signaling"])

# ICE servers configuration for NAT traversal
ICE_SERVERS = [
    RTCIceServer(urls="stun:stun.l.google.com:19302"),
    RTCIceServer(urls="stun:stun1.l.google.com:19302"),
    # Add TURN servers here for production: RTCIceServer(urls="turn:your-turn-server.com:3478", username="", credential="")
]

# Rate limiting: track requests per IP
_rate_limit_store: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_MAX_REQUESTS = 10  # per window
RATE_LIMIT_WINDOW_S = 60

# Keep track of active call sessions to prevent garbage collection.
sessions = {}


def _remove_session(session_id: str):
    clear_session(session_id)
    sessions.pop(session_id, None)


@webrtc_router.post("/offer")
async def offer(request: Request):
    # Rate limiting check
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    _rate_limit_store[client_ip] = [
        ts for ts in _rate_limit_store[client_ip] if now - ts < RATE_LIMIT_WINDOW_S
    ]
    if len(_rate_limit_store[client_ip]) >= RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(status_code=429, detail="Too many requests")
    _rate_limit_store[client_ip].append(now)

    try:
        params = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    if "sdp" not in params or "type" not in params:
        raise HTTPException(status_code=400, detail="Missing sdp or type in payload")

    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    config = RTCConfiguration(iceServers=ICE_SERVERS)
    session = CallSession(
        event_handler=log_gateway_event,
        assistant_handler=handle_transcript,
        on_close=_remove_session,
        rtc_config=config,
    )
    sessions[session.session_id] = session
    logger.info(f"Created new CallSession {session.session_id}")

    try:
        answer = await session.start(offer)

        return JSONResponse(
            content={
                "sdp": answer.sdp,
                "type": answer.type
            }
        )
    except Exception as e:
        logger.error(f"Error creating WebRTC answer: {e}")
        await session.close(reason="setup_failed")
        raise HTTPException(
            status_code=500,
            detail="Failed to establish WebRTC connection",
        )
