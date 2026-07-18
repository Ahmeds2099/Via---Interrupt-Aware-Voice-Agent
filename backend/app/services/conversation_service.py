from app.models.conversation import Message


class ConversationService:

    _sessions: dict[str, list[Message]] = {}

    @classmethod
    def get_messages(cls, session_id: str) -> list[Message]:
        return cls._sessions.get(session_id, [])

    @classmethod
    def add_message(
        cls,
        session_id: str,
        role: str,
        content: str,
    ):

        if session_id not in cls._sessions:
            cls._sessions[session_id] = []

        cls._sessions[session_id].append(
            Message(
                role=role,
                content=content,
            )
        )

    @classmethod
    def clear(cls, session_id: str):

        cls._sessions.pop(session_id, None)