import asyncio
import inspect
import json
import os
import time
import uuid
from typing import Any, Callable, Dict, Optional

from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration

from src.adapters.stt_deepgram import DeepgramSTTAdapter
from src.adapters.tts_factory import create_tts_adapter
from src.gateway.audio_track import AgentAudioTrack, process_inbound_audio
from src.gateway.barge_in import BargeInMetrics
from src.gateway.vad import GatewayVAD
from src.logger import logger

EventHandler = Callable[[Dict[str, Any]], Any]
AssistantHandler = Callable[[Dict[str, Any]], Any]
CloseHandler = Callable[[str], Any]

TTS_KEEPALIVE_INTERVAL_S = 20
POST_BARGE_IN_IGNORE_FINALS_S = 0.6
# Wait after last STT final before replying (merges split long sentences)
UTTERANCE_MERGE_MS = int(os.getenv("STT_UTTERANCE_MERGE_MS", "1200"))


class CallSession:
    """Owns all realtime resources for one active WebRTC call."""

    def __init__(
        self,
        session_id: Optional[str] = None,
        event_handler: Optional[EventHandler] = None,
        assistant_handler: Optional[AssistantHandler] = None,
        on_close: Optional[CloseHandler] = None,
        rtc_config: Optional[RTCConfiguration] = None,
    ):
        self.session_id = session_id or str(uuid.uuid4())
        self.event_handler = event_handler
        self.assistant_handler = assistant_handler
        self.on_close = on_close

        self.pc = RTCPeerConnection(configuration=rtc_config)
        self.agent_track: Optional[AgentAudioTrack] = None
        self.stt: Optional[DeepgramSTTAdapter] = None
        self.tts = None
        self.tasks = set()
        self._closed = False
        self._speak_lock = asyncio.Lock()
        self._speaking = False
        self._speak_generation = 0
        self._barge_in_lock = asyncio.Lock()
        self._ignore_finals_until = 0.0
        self._vad = GatewayVAD()
        self._metrics = BargeInMetrics()
        self._events_channel = None
        self._utterance_parts: list[str] = []
        self._utterance_merge_task: Optional[asyncio.Task] = None

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

        @self.pc.on("datachannel")
        def on_datachannel(channel):
            logger.info(f"Data channel '{channel.label}' for {self.session_id}")
            if channel.label == "events":
                self._events_channel = channel

                @channel.on("message")
                def on_message(message):
                    self._on_client_event(message)

    def _on_client_event(self, message):
        try:
            if isinstance(message, bytes):
                message = message.decode("utf-8")
            data = json.loads(message)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return

        if data.get("type") == "client_speech_start" and self._speaking:
            self._create_task(
                self._handle_barge_in("client_hint"),
                "barge-in-client",
            )

    def _on_inbound_pcm_frame(self, audio_bytes: bytes):
        started, ended, barge_ready = self._vad.process_frame(
            audio_bytes, agent_speaking=self._speaking
        )

        if started:
            self._metrics.speech_started_count += 1
            self._create_task(
                self._emit_event("speech_started", {}),
                "speech-started",
            )

        if ended:
            self._metrics.speech_ended_count += 1
            self._create_task(
                self._emit_event("speech_ended", {}),
                "speech-ended",
            )

        if barge_ready and self._speaking:
            self._create_task(self._handle_barge_in("vad"), "barge-in-vad")

    async def start(self, offer: RTCSessionDescription) -> RTCSessionDescription:
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
        self.tts = create_tts_adapter()

        self.tts.set_callback(self._on_tts_audio)
        self.stt.set_callback(self._on_transcript)

        self._create_task(self.stt.connect(), "deepgram-stt-connect")
        self._create_task(self.tts.connect(), "tts-connect")
        self._create_task(
            process_inbound_audio(
                inbound_track,
                self.stt,
                on_pcm_frame=self._on_inbound_pcm_frame,
            ),
            "inbound-audio-to-stt",
        )
        if os.getenv("TTS_PROVIDER", "deepgram").strip().lower() not in (
            "pyttsx3",
            "offline",
            "local",
        ):
            self._create_task(self._tts_keepalive_loop(), "tts-keepalive")

        self.pc.addTrack(self.agent_track)

    def _on_tts_audio(self, audio_bytes: bytes):
        if not self.agent_track:
            return
        self.agent_track.push_audio(audio_bytes)

    async def _handle_barge_in(self, reason: str):
        async with self._barge_in_lock:
            if not self._speaking:
                return

            self._speak_generation += 1
            self._speaking = False
            self._vad.reset_barge_counter()
            self._metrics.record_barge_in(reason)

            logger.info(f"Barge-in for {self.session_id} ({reason})")
            await self._emit_event("barge_in.detected", {"reason": reason})
            await self._emit_event("speak.cancel", {"reason": reason})

            if self.agent_track:
                self.agent_track.clear_playback()
            if self.tts:
                await self.tts.cancel()

            self._ignore_finals_until = time.monotonic() + POST_BARGE_IN_IGNORE_FINALS_S

    async def _on_transcript(self, text: str, is_final: bool):
        if not text.strip():
            return

        if is_final and time.monotonic() < self._ignore_finals_until:
            self._metrics.ignored_stt_finals += 1
            return

        if self._speaking:
            if not is_final:
                await self._handle_barge_in("stt_partial")
                return
            self._metrics.ignored_stt_finals += 1
            return

        if not is_final:
            await self._emit_event("transcript.partial", {"text": text})
            return

        await self._emit_event("transcript.segment", {"text": text})
        self._utterance_parts.append(text.strip())
        self._schedule_utterance_merge()

    def _schedule_utterance_merge(self):
        if self._utterance_merge_task and not self._utterance_merge_task.done():
            self._utterance_merge_task.cancel()

        async def _merge_and_respond():
            try:
                await asyncio.sleep(UTTERANCE_MERGE_MS / 1000.0)
            except asyncio.CancelledError:
                return

            if self._closed or not self._utterance_parts:
                return

            merged = " ".join(self._utterance_parts).strip()
            self._utterance_parts.clear()
            if not merged:
                return

            logger.info(f"User said (merged) for {self.session_id}: {merged}")
            await self._emit_event("transcript.final", {"text": merged, "merged": True})
            assistant_text = await self._get_assistant_response(merged)
            if assistant_text:
                await self.speak(assistant_text)

        self._utterance_merge_task = self._create_task(
            _merge_and_respond(),
            "utterance-merge",
        )

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

        return f"I heard you say: {text}. "

    async def cancel_speak(self, reason: str = "requested"):
        """Orchestrator/API: stop agent playback (speak.cancel contract)."""
        if self._speaking:
            await self._handle_barge_in(reason)
            return

        if self.agent_track:
            self.agent_track.clear_playback()
        if self.tts:
            await self.tts.cancel()
        await self._emit_event("speak.cancel", {"reason": reason})

    async def speak(self, text: str):
        async with self._speak_lock:
            generation = self._speak_generation
            await self._emit_event("speak.request", {"text": text})

            if not self.tts:
                logger.warning(
                    f"Cannot speak before TTS is ready for {self.session_id}"
                )
                return

            if self.agent_track:
                self.agent_track.clear_playback()

            self._speaking = True
            self._vad.reset_barge_counter()
            try:
                await self.tts.send_text(text)
                if generation != self._speak_generation:
                    return
                await self.tts.flush()
            except Exception as e:
                logger.error(f"speak() failed for {self.session_id}: {e}")
            finally:
                if generation == self._speak_generation:
                    self._speaking = False

    async def _tts_keepalive_loop(self):
        try:
            while not self._closed:
                await asyncio.sleep(TTS_KEEPALIVE_INTERVAL_S)
                if self._closed or not self.tts:
                    continue
                await self.tts.ensure_connected()
        except asyncio.CancelledError:
            pass

    async def close(self, reason: str = "closed"):
        if self._closed:
            return

        self._closed = True
        if self._utterance_merge_task and not self._utterance_merge_task.done():
            self._utterance_merge_task.cancel()
        self._utterance_parts.clear()

        logger.info(
            f"Barge-in metrics for {self.session_id}: {self._metrics.summary()}"
        )
        await self._emit_event("session.end", {"reason": reason, **self._metrics.summary()})

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

        self._send_to_client(event)

        if not self.event_handler:
            return

        result = self.event_handler(event)
        if inspect.isawaitable(result):
            await result

    def _send_to_client(self, event: dict):
        channel = self._events_channel
        if not channel or channel.readyState != "open":
            return
        try:
            channel.send(json.dumps(event))
        except Exception as e:
            logger.debug(f"Could not send event to client: {e}")
