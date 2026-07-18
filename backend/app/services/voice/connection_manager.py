from fastapi import WebSocket
from threading import Lock


class VoiceConnectionManager:
    """
    Manages active WebSocket connections for voice sessions.
    """

    def __init__(self):
        self._connections: dict[str, WebSocket] = {}
        self._lock = Lock()

    async def connect(
        self,
        session_id: str,
        websocket: WebSocket,
    ):
        await websocket.accept()

        with self._lock:
            self._connections[session_id] = websocket

    def disconnect(
        self,
        session_id: str,
    ):
        with self._lock:
            self._connections.pop(session_id, None)

    def get(
        self,
        session_id: str,
    ) -> WebSocket | None:
        with self._lock:
            return self._connections.get(session_id)

    async def send_json(
        self,
        session_id: str,
        payload: dict,
    ):
        websocket = self.get(session_id)

        if websocket is not None:
            await websocket.send_json(payload)

    async def send_bytes(
        self,
        session_id: str,
        data: bytes,
    ):
        websocket = self.get(session_id)

        if websocket is not None:
            await websocket.send_bytes(data)

    @property
    def active_connections(self) -> int:
        with self._lock:
            return len(self._connections)