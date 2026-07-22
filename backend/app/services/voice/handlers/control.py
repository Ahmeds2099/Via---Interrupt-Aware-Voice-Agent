from typing import TYPE_CHECKING

from app.services.voice.connection_manager import VoiceConnectionManager
from app.services.voice.session import VoiceSession

if TYPE_CHECKING:
    from app.services.voice.handlers.audio import AudioHandler


class ControlHandler:
    """
    Placeholder for future control messages.

    Examples:
        - session_close
        - interrupt
        - pause
        - resume
    """

    def __init__(self, audio_handler: "AudioHandler"):

        self.audio_handler = audio_handler

    async def handle(
        self,
        session: VoiceSession,
        connection_manager: VoiceConnectionManager,
        message: dict,
    ) -> None:
        await self.audio_handler.handle_control(
            session=session,
            connection_manager=connection_manager,
            message=message,
        )
