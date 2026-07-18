# pyrefly: ignore [missing-import]
from faster_whisper import WhisperModel

from app.services.stt.base import BaseSTTProvider


class WhisperProvider(BaseSTTProvider):

    def __init__(
        self,
        model_size: str = "base",
    ):

        self.model = WhisperModel(
            model_size,
            device="cpu",
            compute_type="int8",
        )

    def transcribe(
        self,
        audio_path: str,
    ) -> str:

        segments, _ = self.model.transcribe(
            audio_path,
        )

        transcript = ""

        for segment in segments:
            transcript += segment.text

        return transcript.strip()