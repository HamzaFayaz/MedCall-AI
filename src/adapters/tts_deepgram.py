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

    def set_callback(self, callback):
        """
        Set a callback function to handle incoming audio bytes.
        The callback should accept (audio_data: bytes)
        """
        self.on_audio_callback = callback

    async def connect(self):
        try:
            # Create a websocket connection using the async client
            self.connection = self.client.speak.asyncwebsocket.v("1")

            async def on_audio_data(self_param, audio_data, **kwargs):
                if not audio_data:
                    return
                
                if self.on_audio_callback:
                    # Pass the audio bytes back to the gateway/orchestrator
                    if asyncio.iscoroutinefunction(self.on_audio_callback):
                        await self.on_audio_callback(audio_data)
                    else:
                        self.on_audio_callback(audio_data)

            async def on_error(self_param, error, **kwargs):
                logger.error(f"[TTS Error]: {error}")
                
            async def on_flush(self_param, **kwargs):
                logger.debug("[TTS] Audio buffer flushed")

            # Register event handlers
            self.connection.on(SpeakWebSocketEvents.AudioData, on_audio_data)
            self.connection.on(SpeakWebSocketEvents.Error, on_error)
            self.connection.on(SpeakWebSocketEvents.Flushed, on_flush)

            # Configure Deepgram options
            options = SpeakWSOptions(
                model="aura-asteria-en", # You can change the voice model here
                encoding="linear16",
                sample_rate=self.sample_rate,
            )

            logger.info("Connecting to Deepgram TTS...")
            if await self.connection.start(options) is False:
                logger.error("Failed to connect to Deepgram TTS.")
                return False

            logger.info("Deepgram TTS connection established.")
            return True

        except Exception as e:
            logger.error(f"Could not connect to Deepgram TTS: {e}")
            return False

    async def send_text(self, text: str):
        """Send text to Deepgram for speech synthesis."""
        if self.connection:
            try:
                # Send text for TTS processing
                await self.connection.send_text(text)
            except Exception as e:
                logger.error(f"Error sending text to Deepgram TTS: {e}")
                
    async def flush(self):
        """Flush the text buffer to force audio generation."""
        if self.connection:
            try:
                await self.connection.flush()
            except Exception as e:
                logger.error(f"Error flushing Deepgram TTS: {e}")

    async def disconnect(self):
        """Close the Deepgram connection."""
        if self.connection:
            await self.connection.finish()
            logger.info("Deepgram TTS connection closed.")
            self.connection = None
