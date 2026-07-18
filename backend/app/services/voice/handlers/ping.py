from app.services.voice.connection_manager import VoiceConnectionManager
from app.services.voice.schemas import VoiceMessageType
from app.services.voice.session import VoiceSession


class PingHandler:
    """
    Handles ping/pong messages.
    """

    async def handle(
        self,
        session: VoiceSession,
        connection_manager: VoiceConnectionManager,
        message: dict,
    ) -> None:

        session.touch()

        await connection_manager.send_json(
            session.session_id,
            {
                "type": VoiceMessageType.PONG.value,
            },
        )