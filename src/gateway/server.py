from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from aiortc import RTCPeerConnection, RTCSessionDescription
import uuid
import asyncio
from src.logger import logger

from src.gateway.audio_track import AgentAudioTrack
from src.adapters.stt_deepgram import DeepgramSTTAdapter

webrtc_router = APIRouter(prefix="/webrtc", tags=["WebRTC Signaling"])

# Keep track of active peer connections to prevent garbage collection
pcs = set()

@webrtc_router.post("/offer")
async def offer(request: Request):
    try:
        params = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    if "sdp" not in params or "type" not in params:
        raise HTTPException(status_code=400, detail="Missing sdp or type in payload")

    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    # Create the Peer Connection
    pc = RTCPeerConnection()
    pcs.add(pc)

    session_id = str(uuid.uuid4())
    logger.info(f"Created new RTCPeerConnection for session {session_id}")

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        logger.info(f"Connection state for {session_id} is {pc.connectionState}")
        if pc.connectionState == "failed" or pc.connectionState == "closed":
            pcs.discard(pc)
            logger.info(f"Cleaned up connection for {session_id}")

    @pc.on("track")
    def on_track(track):
        logger.info(f"Track {track.kind} received for {session_id}")
        if track.kind == "audio":
            # 1. Setup the STT Adapter
            stt = DeepgramSTTAdapter()
            
            async def on_transcript(text, is_final):
                # For now, we just log it to the console to prove it works!
                # In Card 6, this text will go to our Orchestrator graph.
                if is_final:
                    logger.info(f"🗣️ USER SAID (Final): {text}")
                else:
                    # Optional: uncomment if you want to see the real-time partial guessing
                    # logger.info(f"   (partial): {text}")
                    pass

            stt.set_callback(on_transcript)
            asyncio.create_task(stt.connect())

            # 2. Create the bidirectional track and attach it
            agent_track = AgentAudioTrack(track, stt)
            pc.addTrack(agent_track)
        
    try:
        # Apply the client's offer
        await pc.setRemoteDescription(offer)
        
        # Create and apply our answer
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        return JSONResponse(
            content={
                "sdp": pc.localDescription.sdp,
                "type": pc.localDescription.type
            }
        )
    except Exception as e:
        logger.error(f"Error creating WebRTC answer: {e}")
        pcs.discard(pc)
        raise HTTPException(status_code=500, detail="Failed to establish WebRTC connection")
