from app.services.voice.connection_manager import VoiceConnectionManager
from app.services.voice.session import VoiceSession


class ControlHandler:
    """
    Placeholder for future control messages.

    Examples:
        - session_close
        - interrupt
        - pause
        - resume
    """

    async def handle(
        self,
        session: VoiceSession,
        connection_manager: VoiceConnectionManager,
        message: dict,
    ) -> None:
        pass