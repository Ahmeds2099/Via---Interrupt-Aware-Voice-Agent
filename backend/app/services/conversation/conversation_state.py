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

    def interrupt(self) -> PausedResponse | None:

        if self.current is None:
            return None

        interrupted = self.current

        interrupted.mark_interrupted()

        if interrupted.resumable:

            self.paused.appendleft(
                interrupted
            )

        self.current = None

        return interrupted

    def finish(
        self,
        response_id: str | None = None,
    ) -> None:

        if (
            response_id is None
            or self.current is None
            or self.current.response_id == response_id
        ):
            self.current = None

    def has_paused(self) -> bool:

        return (
            len(self.paused) > 0
        )

    def peek_paused(self) -> PausedResponse | None:

        if not self.paused:
            return None

        return self.paused[0]

    def resume(
        self,
    ) -> PausedResponse | None:

        if not self.paused:
            return None

        self.current = (
            self.paused.popleft()
        )

        return self.current

    def discard_paused(self) -> None:
        """
        Drop the most recently paused response without resuming it.
        Used when the user declines to continue.
        """

        if self.paused:
            self.paused.popleft()

    def acknowledge_segment(
        self,
        response_id: str,
        segment_id: str,
    ) -> bool:

        candidates = []

        if self.current is not None:
            candidates.append(self.current)

        candidates.extend(self.paused)

        for response in candidates:
            if response.response_id == response_id:
                acknowledged = response.acknowledge_segment(
                    segment_id
                )

                if (
                    acknowledged
                    and response is self.current
                    and response.playback_complete
                ):
                    self.current = None

                return acknowledged

        return False

    def clear(self) -> None:

        self.current = None

        self.paused.clear()

    @property
    def paused_count(self) -> int:

        return len(self.paused)
