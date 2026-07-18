from datetime import datetime, timedelta
from threading import Lock

from app.services.voice.session import VoiceSession


class VoiceSessionManager:

    SESSION_TIMEOUT = timedelta(minutes=30)

    def __init__(self):

        self._sessions: dict[str, VoiceSession] = {}

        self._lock = Lock()

    def create_session(self) -> VoiceSession:

        session = VoiceSession()

        with self._lock:

            self._sessions[session.session_id] = session

        return session

    def get_session(
        self,
        session_id: str,
    ) -> VoiceSession | None:

        with self._lock:

            return self._sessions.get(session_id)

    def remove_session(
        self,
        session_id: str,
    ):

        with self._lock:

            self._sessions.pop(session_id, None)

    def touch(
        self,
        session_id: str,
    ):

        session = self.get_session(session_id)

        if session:

            session.touch()

    def cleanup(self):

        now = datetime.utcnow()

        expired = []

        with self._lock:

            for session_id, session in self._sessions.items():

                if now - session.last_activity > self.SESSION_TIMEOUT:

                    expired.append(session_id)

            for session_id in expired:

                self._sessions.pop(session_id)

    def active_sessions(self) -> int:

        with self._lock:

            return len(self._sessions)