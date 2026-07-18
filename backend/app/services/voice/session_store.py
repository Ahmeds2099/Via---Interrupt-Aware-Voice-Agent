from app.services.voice.session import VoiceSession


class VoiceSessionStore:

    def __init__(self):

        self.sessions: dict[str, VoiceSession] = {}

    def get_session(
        self,
        session_id: str,
    ) -> VoiceSession:

        if session_id not in self.sessions:

            self.sessions[session_id] = VoiceSession(
                session_id=session_id,
            )

        return self.sessions[session_id]