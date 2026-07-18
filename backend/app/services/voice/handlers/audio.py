from app.services.voice.connection_manager import VoiceConnectionManager
from app.services.voice.session import VoiceSession
from app.services.voice.stt_pipeline import VoiceSTTPipeline


class AudioHandler:

    MIN_BUFFER_SIZE = 32000

    def __init__(self):

        self.pipeline = VoiceSTTPipeline()

    async def handle(
        self,
        session: VoiceSession,
        connection_manager: VoiceConnectionManager,
        data: bytes,
    ) -> None:

        session.touch()

        session.audio_buffer.append(data)

        print(
            f"[VOICE] Received {len(data)} bytes "
            f"(buffer={session.audio_buffer.size()} bytes)"
        )

        if session.audio_buffer.size() < self.MIN_BUFFER_SIZE:
            return

        transcript = await self.pipeline.process(
            session,
        )

        if transcript:

            print(f"[TRANSCRIPT] {transcript}")