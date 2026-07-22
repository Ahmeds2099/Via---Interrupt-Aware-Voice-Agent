from app.services.stt.base import BaseSTTProvider


class WhisperProvider(BaseSTTProvider):

    def __init__(
        self,
        model_size: str = "base",
    ):

        from app.core.config import settings
        if not settings.VOICE_ALLOW_WHISPER_FALLBACK:
            raise RuntimeError("not available in this deployment")

        # Keep the import and model allocation off the normal Deepgram path.
        from faster_whisper import WhisperModel

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
