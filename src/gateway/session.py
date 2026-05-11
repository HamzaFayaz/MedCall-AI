import asyncio
import inspect
import uuid
from typing import Any, Callable, Dict, Optional

from aiortc import RTCPeerConnection, RTCSessionDescription

from src.adapters.stt_deepgram import DeepgramSTTAdapter
from src.adapters.tts_deepgram import DeepgramTTSAdapter
from src.gateway.audio_track import AgentAudioTrack, process_inbound_audio
from src.logger import logger


EventHandler = Callable[[Dict[str, Any]], Any]
AssistantHandler = Callable[[Dict[str, Any]], Any]
CloseHandler = Callable[[str], Any]


class CallSession:
    """Owns all realtime resources for one active WebRTC call."""

    def __init__(
        self,
        session_id: Optional[str] = None,
        event_handler: Optional[EventHandler] = None,
        assistant_handler: Optional[AssistantHandler] = None,
        on_close: Optional[CloseHandler] = None,
    ):
        self.session_id = session_id or str(uuid.uuid4())
        self.event_handler = event_handler
        self.assistant_handler = assistant_handler
        self.on_close = on_close

        self.pc = RTCPeerConnection()
        self.agent_track: Optional[AgentAudioTrack] = None
        self.stt: Optional[DeepgramSTTAdapter] = None
        self.tts: Optional[DeepgramTTSAdapter] = None
        self.tasks = set()
        self._closed = False

        self._register_peer_connection_handlers()

    def _register_peer_connection_handlers(self):
        @self.pc.on("connectionstatechange")
        async def on_connectionstatechange():
            logger.info(
                f"Connection state for {self.session_id} is {self.pc.connectionState}"
            )
            if self.pc.connectionState in {"disconnected", "failed", "closed"}:
                await self.close(reason=self.pc.connectionState)

        @self.pc.on("track")
        def on_track(track):
            logger.info(f"Track {track.kind} received for {self.session_id}")
            if track.kind == "audio":
                self._attach_audio_track(track)

    async def start(self, offer: RTCSessionDescription) -> RTCSessionDescription:
        """Apply the browser offer and return the backend WebRTC answer."""
        await self._emit_event("session.started", {})

        await self.pc.setRemoteDescription(offer)
        answer = await self.pc.createAnswer()
        await self.pc.setLocalDescription(answer)

        return self.pc.localDescription

    def _attach_audio_track(self, inbound_track):
        if self.agent_track:
            logger.warning(f"Audio track already attached for {self.session_id}")
            return

        self.agent_track = AgentAudioTrack()
        self.stt = DeepgramSTTAdapter()
        self.tts = DeepgramTTSAdapter()

        self.tts.set_callback(self._on_tts_audio)
        self.stt.set_callback(self._on_transcript)

        self._create_task(self.stt.connect(), "deepgram-stt-connect")
        self._create_task(self.tts.connect(), "deepgram-tts-connect")
        self._create_task(
            process_inbound_audio(inbound_track, self.stt),
            "inbound-audio-to-stt",
        )

        self.pc.addTrack(self.agent_track)

    def _on_tts_audio(self, audio_bytes: bytes):
        if not self.agent_track:
            logger.warning(f"TTS audio arrived before audio track for {self.session_id}")
            return

        self.agent_track.queue.put_nowait(audio_bytes)

    async def _on_transcript(self, text: str, is_final: bool):
        event_name = "transcript.final" if is_final else "transcript.partial"
        await self._emit_event(event_name, {"text": text})

        if not is_final:
            return

        logger.info(f"User said final transcript for {self.session_id}: {text}")
        assistant_text = await self._get_assistant_response(text)
        if assistant_text:
            await self.speak(assistant_text)

    async def _get_assistant_response(self, text: str) -> str:
        event = {
            "type": "transcript.final",
            "session_id": self.session_id,
            "text": text,
        }

        if self.assistant_handler:
            result = self.assistant_handler(event)
            if inspect.isawaitable(result):
                result = await result
            if result:
                return str(result)

        # Temporary fallback until the orchestrator is wired in.
        return f"I heard you say: {text}. "

    async def speak(self, text: str):
        await self._emit_event("speak.request", {"text": text})

        if not self.tts:
            logger.warning(f"Cannot speak before TTS is ready for {self.session_id}")
            return

        await self.tts.send_text(text)
        await self.tts.flush()

    async def close(self, reason: str = "closed"):
        if self._closed:
            return

        self._closed = True
        await self._emit_event("session.end", {"reason": reason})

        for task in list(self.tasks):
            task.cancel()

        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
            self.tasks.clear()

        cleanup_tasks = []
        if self.stt:
            cleanup_tasks.append(self.stt.disconnect())
        if self.tts:
            cleanup_tasks.append(self.tts.disconnect())

        if cleanup_tasks:
            results = await asyncio.gather(*cleanup_tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    logger.warning(
                        f"Cleanup error for session {self.session_id}: {result}"
                    )

        if self.pc.connectionState != "closed":
            await self.pc.close()

        if self.on_close:
            result = self.on_close(self.session_id)
            if inspect.isawaitable(result):
                await result

        logger.info(f"Cleaned up session {self.session_id}")

    def _create_task(self, coroutine, name: str):
        task = asyncio.create_task(coroutine, name=f"{self.session_id}:{name}")
        self.tasks.add(task)

        def _on_done(done_task):
            self.tasks.discard(done_task)
            if done_task.cancelled():
                return

            error = done_task.exception()
            if error:
                logger.error(
                    f"Task {name} failed for session {self.session_id}: {error}"
                )

        task.add_done_callback(_on_done)
        return task

    async def _emit_event(self, event_type: str, payload: Dict[str, Any]):
        event = {
            "type": event_type,
            "session_id": self.session_id,
            **payload,
        }

        if not self.event_handler:
            logger.debug(f"Session event: {event}")
            return

        result = self.event_handler(event)
        if inspect.isawaitable(result):
            await result
