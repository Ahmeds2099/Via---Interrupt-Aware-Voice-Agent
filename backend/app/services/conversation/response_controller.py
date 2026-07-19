from __future__ import annotations

from threading import Lock
from uuid import uuid4


class ResponseController:
    """
    Controls the lifecycle of one active assistant response.

    Responsibilities:

    - cancellation
    - interruption
    - completion
    - response identity

    The LLM, StreamingTTS and Cartesia
    all read this controller.
    """

    def __init__(self):

        self._lock = Lock()

        self._response_id: str | None = None

        self._cancelled = False

        self._completed = False

    def begin(self) -> str:

        with self._lock:

            self._response_id = str(
                uuid4()
            )

            self._cancelled = False

            self._completed = False

            return self._response_id

    def cancel(self) -> None:

        with self._lock:

            self._cancelled = True

    def complete(self) -> None:

        with self._lock:

            self._completed = True

    def reset(self) -> None:

        with self._lock:

            self._response_id = None

            self._cancelled = False

            self._completed = False

    @property
    def cancelled(self) -> bool:

        with self._lock:

            return self._cancelled

    @property
    def completed(self) -> bool:

        with self._lock:

            return self._completed

    @property
    def active(self) -> bool:

        with self._lock:

            return (
                self._response_id is not None
                and not self._completed
            )

    @property
    def response_id(self) -> str | None:

        with self._lock:

            return self._response_id