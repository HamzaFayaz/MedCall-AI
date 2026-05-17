import os
import asyncio
from deepgram import (
    DeepgramClient,
    LiveTranscriptionEvents,
    LiveOptions,
)
from src.logger import logger

class DeepgramSTTAdapter:
    def __init__(self, sample_rate: int = 16000, channels: int = 1):
        self.api_key = os.getenv("DEEPGRAM_API_KEY")
        if not self.api_key:
            logger.error("DEEPGRAM_API_KEY environment variable is not set!")

        self.client = DeepgramClient(self.api_key)
        self.connection = None
        self.sample_rate = sample_rate
        self.channels = channels
        self.on_transcript_callback = None
        # ms of silence before Deepgram ends an utterance (was 300; higher = longer sentences stay together)
        self.endpointing_ms = int(os.getenv("STT_ENDPOINTING_MS", "700"))

    def set_callback(self, callback):
        """
        Set a callback function to handle incoming transcripts.
        The callback should accept (text: str, is_final: bool)
        """
        self.on_transcript_callback = callback

    async def connect(self):
        try:
            # Create a websocket connection using the async client
            self.connection = self.client.listen.asyncwebsocket.v("1")

            async def on_message(self_param, result, **kwargs):
                if not result.channel or not result.channel.alternatives:
                    return
                
                sentence = result.channel.alternatives[0].transcript
                if not sentence:
                    return

                is_final = result.is_final
                
                if self.on_transcript_callback:
                    # Pass the transcript back to the gateway/orchestrator
                    if asyncio.iscoroutinefunction(self.on_transcript_callback):
                        await self.on_transcript_callback(sentence, is_final)
                    else:
                        self.on_transcript_callback(sentence, is_final)
                
                if is_final:
                    logger.info(f"[STT Final]: {sentence}")

            async def on_error(self_param, error, **kwargs):
                logger.error(f"[STT Error]: {error}")

            # Register event handlers
            self.connection.on(LiveTranscriptionEvents.Transcript, on_message)
            self.connection.on(LiveTranscriptionEvents.Error, on_error)

            # Configure Deepgram options (using the medical model for this hospital use case)
            options = LiveOptions(
                model="nova-2-medical",
                language="en",
                encoding="linear16",
                channels=self.channels,
                sample_rate=self.sample_rate,
                interim_results=True,
                endpointing=self.endpointing_ms,
                smart_format=True,
            )

            logger.info(
                f"Connecting to Deepgram STT (endpointing={self.endpointing_ms}ms)..."
            )
            if await self.connection.start(options) is False:
                logger.error("Failed to connect to Deepgram STT.")
                return False

            logger.info("Deepgram STT connection established.")
            return True

        except Exception as e:
            logger.error(f"Could not connect to Deepgram: {e}")
            return False

    async def send_audio(self, audio_data: bytes):
        """Send raw audio bytes to Deepgram."""
        if self.connection:
            try:
                await self.connection.send(audio_data)
            except Exception as e:
                logger.error(f"Error sending audio to Deepgram: {e}")

    async def disconnect(self):
        """Close the Deepgram connection."""
        if self.connection:
            await self.connection.finish()
            logger.info("Deepgram STT connection closed.")
            self.connection = None
