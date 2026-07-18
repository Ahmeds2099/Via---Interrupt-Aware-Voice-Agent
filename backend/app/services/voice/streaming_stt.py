from app.services.stt.factory import STTFactory
from app.services.voice.session import VoiceSession


class StreamingSTT:
    """
    Handles incremental audio for a voice session.
    """

    MIN_BUFFER_SIZE = 32000

    def __init__(self):
        self.provider = STTFactory.get_provider()

    def append_audio(
        self,
        session: VoiceSession,
        chunk: bytes,
    ) -> str | None:

        session.audio_buffer.append(chunk)

        if session.audio_buffer.size() < self.MIN_BUFFER_SIZE:
            return None

        audio = session.audio_buffer.getvalue()

        session.audio_buffer.clear()

        return self.provider.transcribe(audio)