import os
import asyncio
from deepgram import (
    DeepgramClient,
    SpeakWebSocketEvents,
    SpeakWSOptions,
)
from src.logger import logger


class DeepgramTTSAdapter:
    def __init__(self, sample_rate: int = 16000):
        self.api_key = os.getenv("DEEPGRAM_API_KEY")
        if not self.api_key:
            logger.error("DEEPGRAM_API_KEY environment variable is not set!")

        self.client = DeepgramClient(self.api_key)
        self.connection = None
        self.sample_rate = sample_rate
        self.on_audio_callback = None
        self._connected = False
        self._connect_lock = asyncio.Lock()

    def set_callback(self, callback):
        """Callback receives streaming PCM audio bytes."""
        self.on_audio_callback = callback

    def _mark_disconnected(self):
        self._connected = False

    async def connect(self):
        async with self._connect_lock:
            if self.connection:
                try:
                    await self.connection.finish()
                except Exception:
                    pass
                self.connection = None

            try:
                self.connection = self.client.speak.asyncwebsocket.v("1")

                async def on_audio_data(*args, **kwargs):
                    audio_data = kwargs.get("data")
                    if not audio_data:
                        for arg in args:
                            if isinstance(arg, bytes):
                                audio_data = arg
                                break
                    if not audio_data or not self.on_audio_callback:
                        return
                    if asyncio.iscoroutinefunction(self.on_audio_callback):
                        await self.on_audio_callback(audio_data)
                    else:
                        self.on_audio_callback(audio_data)

                async def on_error(self_param, error, **kwargs):
                    logger.error(f"[TTS Error]: {error}")
                    self._mark_disconnected()

                async def on_close(self_param, *args, **kwargs):
                    logger.info("[TTS] WebSocket closed")
                    self._mark_disconnected()

                async def on_flush(self_param, **kwargs):
                    logger.debug("[TTS] Audio buffer flushed")

                self.connection.on(SpeakWebSocketEvents.AudioData, on_audio_data)
                self.connection.on(SpeakWebSocketEvents.Error, on_error)
                self.connection.on(SpeakWebSocketEvents.Close, on_close)
                self.connection.on(SpeakWebSocketEvents.Flushed, on_flush)

                options = SpeakWSOptions(
                    model="aura-asteria-en",
                    encoding="linear16",
                    sample_rate=self.sample_rate,
                )

                logger.info("Connecting to Deepgram TTS...")
                if await self.connection.start(options) is False:
                    logger.error("Failed to connect to Deepgram TTS.")
                    self._mark_disconnected()
                    return False

                self._connected = True
                logger.info("Deepgram TTS connection established.")
                return True

            except Exception as e:
                logger.error(f"Could not connect to Deepgram TTS: {e}")
                self._mark_disconnected()
                return False

    async def _is_live(self) -> bool:
        if not self.connection or not self._connected:
            return False
        if hasattr(self.connection, "is_connected"):
            res = self.connection.is_connected()
            if asyncio.iscoroutine(res):
                res = await res
            if not res:
                self._mark_disconnected()
            return bool(res)
        return True

    async def ensure_connected(self) -> bool:
        if await self._is_live():
            return True
        logger.info("TTS reconnecting...")
        return await self.connect()

    async def cancel(self):
        """Stop in-flight synthesis (barge-in / speak.cancel)."""
        if not self.connection:
            return
        try:
            if await self._is_live():
                await self.connection.clear()
        except Exception as e:
            logger.warning(f"TTS clear failed: {e}")
            self._mark_disconnected()

    async def send_text(self, text: str):
        if not await self.ensure_connected():
            raise RuntimeError("Deepgram TTS is not connected")

        try:
            await self.connection.send_text(text)
        except Exception as e:
            logger.warning(f"TTS send_text failed: {e}. Reconnecting...")
            self._mark_disconnected()
            if not await self.ensure_connected():
                raise
            await self.connection.send_text(text)

    async def flush(self):
        if not await self.ensure_connected():
            raise RuntimeError("Deepgram TTS is not connected")

        try:
            await self.connection.flush()
        except Exception as e:
            logger.warning(f"TTS flush failed: {e}. Reconnecting...")
            self._mark_disconnected()
            if await self.ensure_connected():
                await self.connection.flush()
            else:
                raise

    async def disconnect(self):
        if self.connection:
            try:
                await self.connection.finish()
            except Exception:
                pass
            logger.info("Deepgram TTS connection closed.")
            self.connection = None
        self._mark_disconnected()
