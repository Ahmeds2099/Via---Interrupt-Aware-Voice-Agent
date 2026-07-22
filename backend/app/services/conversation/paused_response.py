from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from threading import Event, Lock
from uuid import uuid4


@dataclass(slots=True)
class PausedResponse:
    """
    Represents a response that was interrupted before completion.

    This object is intentionally model-agnostic.

    Future VFs (Hume, long-term memory, conversation planning)
    can extend it without changing the interruption pipeline.
    """

    response_id: str = field(
        default_factory=lambda: str(uuid4())
    )

    session_id: str = ""

    #
    # Original user request
    #
    query: str = ""

    #
    # Prompt that generated the response.
    #
    prompt: list[dict] = field(
        default_factory=list
    )

    #
    # Retrieved RAG chunks.
    #
    chunks: list[dict] = field(
        default_factory=list
    )

    #
    # Assistant text already generated.
    #
    generated_text: str = ""

    #
    # Assistant text already spoken.
    #
    spoken_text: str = ""

    #
    # Whether Via should attempt to resume.
    #
    resumable: bool = True

    created_at: datetime = field(
        default_factory=datetime.utcnow
    )

    interrupted_at: datetime | None = None

    _segment_ends: dict[str, int] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )

    _acknowledged_chars: int = field(
        default=0,
        init=False,
        repr=False,
    )

    _lock: Lock = field(
        default_factory=Lock,
        init=False,
        repr=False,
    )

    _generation_done: Event = field(
        default_factory=Event,
        init=False,
        repr=False,
    )

    def append_generated(
        self,
        token: str,
    ) -> None:

        with self._lock:
            self.generated_text += token

    def append_spoken(
        self,
        text: str,
    ) -> None:

        with self._lock:
            self.spoken_text += text

    def register_segment(
        self,
        segment_id: str,
        end_offset: int,
    ) -> None:

        with self._lock:
            self._segment_ends[segment_id] = end_offset

    def acknowledge_segment(
        self,
        segment_id: str,
    ) -> bool:

        with self._lock:
            end_offset = self._segment_ends.get(segment_id)
            if end_offset is None:
                return False

            self._acknowledged_chars = max(
                self._acknowledged_chars,
                end_offset,
            )
            self.spoken_text = self.generated_text[
                : self._acknowledged_chars
            ]
            return True

    def consume_remaining(self, characters: int) -> None:
        """Advance a resumed response after confirmed playback."""

        if characters <= 0:
            return

        with self._lock:
            self._acknowledged_chars = min(
                len(self.generated_text),
                self._acknowledged_chars + characters,
            )
            self.spoken_text = self.generated_text[
                : self._acknowledged_chars
            ]

    def mark_interrupted(self) -> None:

        self.interrupted_at = datetime.utcnow()

    def mark_generation_complete(self) -> None:

        self._generation_done.set()

    def wait_for_generation(
        self,
        timeout: float | None = None,
    ) -> bool:

        return self._generation_done.wait(timeout)

    @property
    def remaining_text(self) -> str:

        with self._lock:
            return self.generated_text[
                self._acknowledged_chars:
            ]

    @property
    def acknowledged_text(self) -> str:

        with self._lock:
            return self.generated_text[
                : self._acknowledged_chars
            ]

    @property
    def playback_complete(self) -> bool:

        with self._lock:
            return (
                self._generation_done.is_set()
                and self._acknowledged_chars
                >= len(self.generated_text)
            )

    @property
    def complete(self) -> bool:

        return (
            self._generation_done.is_set()
            and self.remaining_text.strip() == ""
        )
