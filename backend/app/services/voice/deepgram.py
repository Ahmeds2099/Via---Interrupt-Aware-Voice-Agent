from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Awaitable, Callable
from urllib.parse import urlencode

# pyrefly: ignore [missing-import]
import websockets

from app.core.config import settings


@dataclass(frozen=True, slots=True)
class TranscriptEvent:
    text: str
    is_final: bool
    speech_final: bool = False
    confidence: float | None = None
    provider: str = "deepgram"


TranscriptHandler = Callable[[TranscriptEvent], Awaitable[None]]
ErrorHandler = Callable[[str], Awaitable[None]]


_VIA_NAME = re.compile(
    r"\b(?:vee[\s-]?(?:ah|uh)|veeya|viah)\b",
    re.IGNORECASE,
)


def normalize_transcript(text: str) -> str:
    """Normalize strong phonetic renderings of Via's name."""

    return _VIA_NAME.sub("Via", text).strip()


class DeepgramStreamingSTT:
    """One Deepgram live-transcription connection per voice session."""

    BASE_URL = "wss://api.deepgram.com/v1/listen"
    KEEPALIVE_SECONDS = 4.0

    def __init__(
        self,
        on_transcript: TranscriptHandler,
        on_error: ErrorHandler,
    ) -> None:
        self.on_transcript = on_transcript
        self.on_error = on_error

        self.websocket = None
        self.send_queue: asyncio.Queue[bytes | str] = asyncio.Queue(
            maxsize=128,
        )
        self.sender_task: asyncio.Task | None = None
        self.receiver_task: asyncio.Task | None = None
        self.keepalive_task: asyncio.Task | None = None

        self.final_parts: list[str] = []
        self.started = False
        self.closing = False
        self.failed = False

    @staticmethod
    def _url() -> str:
        params = [
            ("model", settings.DEEPGRAM_MODEL),
            ("language", settings.DEEPGRAM_LANGUAGE),
            ("encoding", "linear16"),
            ("sample_rate", "16000"),
            ("channels", "1"),
            ("interim_results", "true"),
            ("vad_events", "true"),
            ("smart_format", "true"),
            ("punctuate", "true"),
            ("numerals", "true"),
            ("endpointing", str(settings.DEEPGRAM_ENDPOINTING_MS)),
            (
                "utterance_end_ms",
                str(settings.DEEPGRAM_UTTERANCE_END_MS),
            ),
        ]

        for keyword in settings.DEEPGRAM_KEYWORDS.split(","):
            keyword = keyword.strip()
            if keyword:
                params.append(("keywords", keyword))

        return (
            f"{DeepgramStreamingSTT.BASE_URL}?"
            f"{urlencode(params)}"
        )

    async def start(self) -> None:
        if self.started:
            return

        if not settings.DEEPGRAM_API_KEY:
            raise RuntimeError("DEEPGRAM_API_KEY is not configured")

        self.websocket = await websockets.connect(
            self._url(),
            additional_headers={
                "Authorization": (
                    f"Token {settings.DEEPGRAM_API_KEY}"
                ),
            },
            open_timeout=10,
            close_timeout=3,
            max_size=2**22,
        )
        self.started = True

        self.sender_task = asyncio.create_task(
            self._sender(),
            name="deepgram-sender",
        )
        self.receiver_task = asyncio.create_task(
            self._receiver(),
            name="deepgram-receiver",
        )
        self.keepalive_task = asyncio.create_task(
            self._keepalive(),
            name="deepgram-keepalive",
        )

    async def send_audio(self, audio: bytes) -> None:
        if not self.started or self.closing or self.failed:
            return

        try:
            self.send_queue.put_nowait(audio)
        except asyncio.QueueFull:
            await self._fail("Deepgram audio queue overflowed")

    async def _sender(self) -> None:
        try:
            while not self.closing:
                payload = await self.send_queue.get()
                if self.websocket is None:
                    return
                await self.websocket.send(payload)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self._fail(f"Deepgram send failed: {exc}")

    async def _receiver(self) -> None:
        try:
            if self.websocket is None:
                return

            async for raw_message in self.websocket:
                if isinstance(raw_message, bytes):
                    continue

                message = json.loads(raw_message)
                await self._handle_message(message)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self._fail(f"Deepgram stream failed: {exc}")

    async def _handle_message(self, message: dict) -> None:
        message_type = message.get("type")

        if message_type == "Results":
            channel = message.get("channel") or {}
            alternatives = channel.get("alternatives") or []
            if not alternatives:
                return

            alternative = alternatives[0]
            text = normalize_transcript(
                alternative.get("transcript") or ""
            )
            confidence = alternative.get("confidence")
            is_final = bool(message.get("is_final"))
            speech_final = bool(message.get("speech_final"))

            if is_final and text:
                self.final_parts.append(text)

            if speech_final:
                await self._emit_final(confidence)
                return

            if not is_final and text:
                committed = " ".join(self.final_parts).strip()
                interim = " ".join(
                    part for part in (committed, text) if part
                )
                await self.on_transcript(
                    TranscriptEvent(
                        text=interim,
                        is_final=False,
                        confidence=confidence,
                    )
                )
            return

        if message_type == "UtteranceEnd":
            await self._emit_final(None)
            return

        if message_type == "Error":
            description = (
                message.get("description")
                or message.get("message")
                or "Deepgram returned an error"
            )
            await self._fail(str(description))

    async def _emit_final(self, confidence: float | None) -> None:
        text = " ".join(self.final_parts).strip()
        self.final_parts.clear()

        if not text:
            return

        await self.on_transcript(
            TranscriptEvent(
                text=text,
                is_final=True,
                speech_final=True,
                confidence=confidence,
            )
        )

    async def _keepalive(self) -> None:
        try:
            while not self.closing:
                await asyncio.sleep(self.KEEPALIVE_SECONDS)
                if self.closing:
                    return
                try:
                    self.send_queue.put_nowait(
                        json.dumps({"type": "KeepAlive"})
                    )
                except asyncio.QueueFull:
                    await self._fail(
                        "Deepgram keepalive queue overflowed"
                    )
                    return
        except asyncio.CancelledError:
            raise

    async def _fail(self, reason: str) -> None:
        if self.failed or self.closing:
            return
        self.failed = True
        asyncio.create_task(self.on_error(reason))

    async def close(self) -> None:
        if self.closing:
            return

        self.closing = True

        if self.websocket is not None:
            try:
                await self.websocket.send(
                    json.dumps({"type": "CloseStream"})
                )
            except Exception:
                pass

        current = asyncio.current_task()
        tasks = (
            self.sender_task,
            self.receiver_task,
            self.keepalive_task,
        )
        for task in tasks:
            if task is not None and task is not current:
                task.cancel()

        for task in tasks:
            if task is None or task is current:
                continue
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

        if self.websocket is not None:
            try:
                await self.websocket.close()
            except Exception:
                pass

        self.started = False
