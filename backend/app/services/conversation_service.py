from __future__ import annotations

from threading import Lock

from app.models.conversation import Message
from app.services.session_repository import session_repository


class ConversationService:
    _sessions: dict[str, list[Message]] = {}
    _clients: dict[str, str] = {}
    _states: dict[str, dict] = {}
    _lock = Lock()

    @classmethod
    def bind(cls, session_id: str, client_id: str) -> dict:
        state = session_repository.load(client_id)
        messages = [
            Message(role=item["role"], content=item["content"])
            for item in state.get("messages", [])
            if item.get("role") and item.get("content")
        ]
        with cls._lock:
            cls._clients[session_id] = client_id
            cls._states[client_id] = state
            cls._sessions[session_id] = messages
        return state

    @classmethod
    def get_messages(cls, session_id: str) -> list[Message]:
        with cls._lock:
            return list(cls._sessions.get(session_id, []))

    @classmethod
    def get_state(cls, session_id: str) -> dict:
        with cls._lock:
            client_id = cls._clients.get(session_id, session_id)
            return dict(cls._states.get(client_id, {}))

    @classmethod
    def update_state(cls, session_id: str, **changes) -> None:
        with cls._lock:
            client_id = cls._clients.get(session_id, session_id)
            state = dict(
                cls._states.get(client_id)
                or session_repository.load(client_id)
            )
            state.update(changes)
            cls._states[client_id] = state
        session_repository.save(client_id, state)

    @classmethod
    def add_message(cls, session_id: str, role: str, content: str) -> None:
        message = Message(role=role, content=content)
        with cls._lock:
            cls._sessions.setdefault(session_id, []).append(message)
            client_id = cls._clients.get(session_id, session_id)
            state = dict(
                cls._states.get(client_id)
                or session_repository.load(client_id)
            )
            state["messages"] = [
                item.model_dump()
                for item in cls._sessions[session_id][-40:]
            ]
            cls._states[client_id] = state
        session_repository.save(client_id, state)

    @classmethod
    def add_memory(cls, client_id: str, memory_id: str, text: str) -> None:
        state = session_repository.load(client_id)
        memories = list(state.get("memories", []))
        if not any(item.get("text") == text for item in memories):
            memories.append({"memory_id": memory_id, "text": text})
        state["memories"] = memories[-50:]
        session_repository.save(client_id, state)
        with cls._lock:
            cls._states[client_id] = state

    @classmethod
    def clear(cls, session_id: str) -> None:
        with cls._lock:
            cls._sessions.pop(session_id, None)
            cls._clients.pop(session_id, None)
