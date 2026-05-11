from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from aiortc import RTCSessionDescription
from src.logger import logger

from src.gateway.session import CallSession

webrtc_router = APIRouter(prefix="/webrtc", tags=["WebRTC Signaling"])

# Keep track of active call sessions to prevent garbage collection.
sessions = {}


def _remove_session(session_id: str):
    sessions.pop(session_id, None)


@webrtc_router.post("/offer")
async def offer(request: Request):
    try:
        params = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    if "sdp" not in params or "type" not in params:
        raise HTTPException(status_code=400, detail="Missing sdp or type in payload")

    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    session = CallSession(on_close=_remove_session)
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
