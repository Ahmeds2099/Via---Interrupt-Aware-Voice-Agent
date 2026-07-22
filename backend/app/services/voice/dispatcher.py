from app.services.voice.connection_manager import VoiceConnectionManager
from app.services.voice.handlers import (
    AudioHandler,
    ControlHandler,
    PingHandler,
)
from app.services.voice.schemas import VoiceMessageType
from app.services.voice.session import VoiceSession


class VoiceDispatcher:
    """
    Dispatches incoming WebSocket messages
    to the appropriate handler.
    """

    def __init__(self):

        self.audio_handler = AudioHandler()

        self._handlers = {
            VoiceMessageType.PING.value: PingHandler(),
            VoiceMessageType.AUDIO.value: self.audio_handler,
        }

        self._control_handler = ControlHandler(
            self.audio_handler
        )

    async def start_session(
        self,
        session: VoiceSession,
        connection_manager: VoiceConnectionManager,
    ) -> None:

        await self.audio_handler.start_session(
            session,
            connection_manager,
        )

    async def close_session(
        self,
        session: VoiceSession,
    ) -> None:

        await session.close()

    async def dispatch(
        self,
        session: VoiceSession,
        connection_manager: VoiceConnectionManager,
        message: dict,
    ) -> None:

        message_type = message.get("type")

        handler = self._handlers.get(message_type)

        if handler is not None:

            await handler.handle(
                session=session,
                connection_manager=connection_manager,
                message=message,
            )

            return

        await self._control_handler.handle(
            session=session,
            connection_manager=connection_manager,
            message=message,
        )

    async def dispatch_audio(
        self,
        session: VoiceSession,
        connection_manager: VoiceConnectionManager,
        data: bytes,
    ):

        handler = self._handlers["audio"]

        await handler.handle(
            session=session,
            connection_manager=connection_manager,
            data=data,
        )

