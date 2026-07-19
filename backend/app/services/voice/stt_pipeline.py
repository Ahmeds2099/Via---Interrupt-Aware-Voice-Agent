import os
import tempfile
import wave

from app.services.stt.factory import STTFactory
from app.services.voice.session import VoiceSession


class VoiceSTTPipeline:
    """
    Converts completed speech segments into
    transcripts using the configured STT provider.
    """

    SAMPLE_RATE = 16000
    CHANNELS = 1
    SAMPLE_WIDTH = 2

    def __init__(self):

        self.provider = STTFactory.get_provider()

    async def process(
        self,
        session: VoiceSession,
        audio: bytes,
    ) -> str | None:

        if not audio:
            return None

        temp_path = None

        try:

            with tempfile.NamedTemporaryFile(
                suffix=".wav",
                delete=False,
            ) as tmp:

                temp_path = tmp.name

            with wave.open(temp_path, "wb") as wav:

                wav.setnchannels(self.CHANNELS)
                wav.setsampwidth(self.SAMPLE_WIDTH)
                wav.setframerate(self.SAMPLE_RATE)
                wav.writeframes(audio)

            transcript = self.provider.transcribe(
                temp_path,
            )

            return transcript

        finally:

            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)