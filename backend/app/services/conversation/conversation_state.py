from __future__ import annotations

from collections import deque

from app.services.conversation.paused_response import (
    PausedResponse,
)


class ConversationState:
    """
    Stores runtime conversation state.

    Unlike ConversationService,
    this class does NOT store history.

    It stores active runtime objects
    that exist only while Via is running.

    Future VFs:

    - interruption
    - topic switching
    - response resumption
    - proactive continuation
    """

    def __init__(self):

        self.current: PausedResponse | None = None

        self.paused: deque[
            PausedResponse
        ] = deque()

    def begin(
        self,
        response: PausedResponse,
    ) -> None:

        self.current = response

    def interrupt(self) -> None:

        if self.current is None:
            return

        self.current.mark_interrupted()

        if self.current.resumable:

            self.paused.appendleft(
                self.current
            )

        self.current = None

    def finish(self) -> None:

        self.current = None

    def has_paused(self) -> bool:

        return (
            len(self.paused) > 0
        )

    def resume(
        self,
    ) -> PausedResponse | None:

        if not self.paused:
            return None

        self.current = (
            self.paused.popleft()
        )

        return self.current

    def clear(self) -> None:

        self.current = None

        self.paused.clear()

    @property
    def paused_count(self) -> int:

        return len(self.paused)