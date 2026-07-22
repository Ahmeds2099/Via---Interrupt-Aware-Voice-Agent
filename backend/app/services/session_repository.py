from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock

import requests

from app.core.config import settings


class SessionRepository:
    """Upstash REST persistence with a process-local safety fallback."""

    SESSION_TTL_SECONDS = 24 * 60 * 60
    MEMORY_TTL_SECONDS = 30 * 24 * 60 * 60

    def __init__(self) -> None:
        self.url = settings.UPSTASH_REDIS_REST_URL.rstrip("/")
        self.token = settings.UPSTASH_REDIS_REST_TOKEN
        self._fallback: dict[str, dict] = {}
        self._lock = Lock()
        self._degraded = not bool(self.url and self.token)
        self._last_error = (
            "Upstash credentials are not configured"
            if self._degraded
            else ""
        )

    @staticmethod
    def _key(client_id: str) -> str:
        return f"via:session:{client_id}"

    @staticmethod
    def _memory_key(client_id: str) -> str:
        return f"via:memories:{client_id}"

    @property
    def status(self) -> dict:
        return {
            "provider": "upstash" if self.url and self.token else "memory",
            "status": "degraded" if self._degraded else "ready",
            "message": self._last_error,
        }

    def _command(self, command: list) -> object:
        response = requests.post(
            self.url,
            headers={"Authorization": f"Bearer {self.token}"},
            json=command,
            timeout=4,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("error"):
            raise RuntimeError(str(payload["error"]))
        return payload.get("result")

    @staticmethod
    def _empty_state(client_id: str) -> dict:
        return {
            "version": 1,
            "client_id": client_id,
            "messages": [],
            "memories": [],
            "active_documents": [],
            "emotion_state": {},
            "doubt_counter": 0,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def load(self, client_id: str) -> dict:
        if self.url and self.token:
            try:
                raw = self._command(["GET", self._key(client_id)])
                memory_raw = self._command(
                    ["GET", self._memory_key(client_id)]
                )
                self._degraded = False
                self._last_error = ""
                if raw:
                    state = json.loads(str(raw))
                    state["memories"] = (
                        json.loads(str(memory_raw))
                        if memory_raw
                        else []
                    )
                    with self._lock:
                        self._fallback[client_id] = deepcopy(state)
                    return state
            except Exception as exc:
                self._degraded = True
                self._last_error = f"Upstash unavailable: {exc}"

        with self._lock:
            return deepcopy(
                self._fallback.get(client_id)
                or self._empty_state(client_id)
            )

    def save(self, client_id: str, state: dict) -> None:
        state = deepcopy(state)
        state["version"] = 1
        state["client_id"] = client_id
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._fallback[client_id] = deepcopy(state)

        if not (self.url and self.token):
            self._degraded = True
            return

        try:
            session_state = dict(state)
            memories = session_state.pop("memories", [])
            self._command(
                [
                    "SET",
                    self._key(client_id),
                    json.dumps(session_state, ensure_ascii=False),
                    "EX",
                    self.SESSION_TTL_SECONDS,
                ]
            )
            self._command(
                [
                    "SET",
                    self._memory_key(client_id),
                    json.dumps(memories, ensure_ascii=False),
                    "EX",
                    self.MEMORY_TTL_SECONDS,
                ]
            )
            self._degraded = False
            self._last_error = ""
        except Exception as exc:
            self._degraded = True
            self._last_error = f"Upstash unavailable: {exc}"

    def ping(self) -> bool:
        if not (self.url and self.token):
            return False
        try:
            self._command(["PING"])
            self._degraded = False
            self._last_error = ""
            return True
        except Exception as exc:
            self._degraded = True
            self._last_error = f"Upstash unavailable: {exc}"
            return False


session_repository = SessionRepository()
