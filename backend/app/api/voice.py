from fastapi import APIRouter
from fastapi import WebSocket
from fastapi import WebSocketDisconnect
import json

from app.services.voice.connection_manager import VoiceConnectionManager
from app.services.voice.schemas import VoiceMessageType
from app.services.voice.session_manager import VoiceSessionManager
from app.services.voice.dispatcher import VoiceDispatcher

router = APIRouter()

connection_manager = VoiceConnectionManager()
session_manager = VoiceSessionManager()
dispatcher = VoiceDispatcher()

@router.websocket("/ws/voice")
async def voice_socket(
    websocket: WebSocket,
):
    session = session_manager.create_session()

    await connection_manager.connect(
        session.session_id,
        websocket,
    )

    await connection_manager.send_json(
        session.session_id,
        {
            "type": VoiceMessageType.CONNECTED,
            "session_id": session.session_id,
        },
    )

    try:
        await dispatcher.start_session(
            session=session,
            connection_manager=connection_manager,
        )

        while True:

            message = await websocket.receive()

            if message["type"] == "websocket.disconnect":
                break

            if message.get("text") is not None:

                await dispatcher.dispatch(
                    session=session,
                    connection_manager=connection_manager,
                    message=json.loads(message["text"]),
                )

            elif message.get("bytes") is not None:

                await dispatcher.dispatch_audio(
                    session=session,
                    connection_manager=connection_manager,
                    data=message["bytes"],
                )

    except WebSocketDisconnect:
        pass

    finally:

        await dispatcher.close_session(session)

        connection_manager.disconnect(
            session.session_id,
        )

    session_manager.remove_session(
        session.session_id,
    )
