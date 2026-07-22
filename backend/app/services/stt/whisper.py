from app.services.stt.base import BaseSTTProvider


class WhisperProvider(BaseSTTProvider):

    def __init__(
        self,
        model_size: str = "base",
    ):

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
