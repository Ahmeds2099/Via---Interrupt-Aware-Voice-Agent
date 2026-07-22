from __future__ import annotations

from app.services.conversation.response_controller import (
    ResponseController,
)
from app.services.tts.factory import TTSFactory


class StreamingTTS:
    """
    Streaming TTS pipeline.

    Responsibilities
    ----------------
    • Buffer incoming LLM tokens.
    • Produce sentence-sized chunks.
    • Stream each chunk immediately.
    • Cooperatively support cancellation.

    StreamingTTS never decides WHEN to stop.
    It simply obeys ResponseController.
    """

    def __init__(self):

        self.provider = TTSFactory.get_provider()

        self.buffer = ""

        self.controller: ResponseController | None = None

    def attach(
        self,
        controller: ResponseController,
    ) -> None:
        """
        Attach the active response controller.
        """

        self.controller = controller

    def detach(self) -> None:

        self.controller = None

    def cancelled(self) -> bool:

        return (
            self.controller is not None
            and self.controller.cancelled
        )

    def feed(
        self,
        token: str,
    ):

        sentence = self.append(token)

        if sentence is None:
            return

        yield from self.stream_sentence(sentence)

    def append(
        self,
        token: str,
    ) -> str | None:

        #
        # Immediate interruption support.
        #
        if self.cancelled():

            print("[TTS] Cancelled")

            self.buffer = ""

            return None

        self.buffer += token

        if not self._ready():
            return None

        sentence = self.buffer

        self.buffer = ""

        return sentence

    def stream_sentence(
        self,
        sentence: str,
    ):

        for audio in self.provider.stream(sentence):

            if self.cancelled():

                print(
                    "[TTS] Interrupted during synthesis"
                )

                self.buffer = ""

                return

            yield audio

    def flush(self):

        sentence = self.flush_text()

        if sentence is None:
            return

        yield from self.stream_sentence(sentence)

    def flush_text(self) -> str | None:

        if self.cancelled():

            self.buffer = ""

            return None

        if not self.buffer.strip():
            return None

        sentence = self.buffer

        self.buffer = ""

        return sentence

    def reset(self):

        self.buffer = ""

    def _ready(self):

        if len(self.buffer) >= 80:
            return True

        return any(
            self.buffer.endswith(x)
            for x in (
                ".",
                "!",
                "?",
                "\n",
            )
        )
