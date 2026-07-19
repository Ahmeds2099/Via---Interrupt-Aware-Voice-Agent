from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
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
    # Remaining assistant text.
    #
    remaining_text: str = ""

    #
    # Whether Via should attempt to resume.
    #
    resumable: bool = True

    created_at: datetime = field(
        default_factory=datetime.utcnow
    )

    interrupted_at: datetime | None = None

    def append_generated(
        self,
        token: str,
    ) -> None:

        self.generated_text += token

    def append_spoken(
        self,
        text: str,
    ) -> None:

        self.spoken_text += text

    def mark_interrupted(self) -> None:

        self.interrupted_at = datetime.utcnow()

        if self.generated_text.startswith(
            self.spoken_text
        ):
            self.remaining_text = (
                self.generated_text[
                    len(self.spoken_text):
                ]
            )
        else:
            self.remaining_text = ""

    @property
    def complete(self) -> bool:

        return (
            self.remaining_text.strip() == ""
        )