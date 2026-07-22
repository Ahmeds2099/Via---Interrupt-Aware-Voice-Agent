from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from time import monotonic

import os


class SpeechStart:
    """
    Emitted immediately when VAD detects
    the beginning of user speech.
    Used only to interrupt assistant playback.
    """
    pass


@dataclass
class SpeechSegment:
    audio: bytes


class VoiceActivityDetector:

    FRAME_BYTES = 1024
    MAX_SEGMENT_SECONDS = 15
    SAMPLE_RATE = 16000
    SAMPLE_WIDTH = 2

    MAX_SEGMENT_BYTES = (
        MAX_SEGMENT_SECONDS
        * SAMPLE_RATE
        * SAMPLE_WIDTH
    )

    # 250 ms. Short confirmations such as "yes" must reach the
    # fallback/resume intent classifier.
    MIN_SEGMENT_BYTES = 8000

    def __init__(self):

        provider = os.getenv("VOICE_VAD_PROVIDER", "silero").lower()
        if provider == "energy":
            from app.services.voice.energy import EnergyEngine
            self.engine = EnergyEngine()
        else:
            from app.services.voice.silero import SileroEngine
            self.engine = SileroEngine()

        self.frame_buffer = bytearray()
        self.segment_buffer = bytearray()

        self.collecting = False
        self.start_emitted = False

        self.last_voice = monotonic()

        self.events = deque()

    def reset(self):

        self.frame_buffer.clear()
        self.segment_buffer.clear()

        self.collecting = False
        self.start_emitted = False

        self.last_voice = monotonic()

        self.engine.reset()

    def update(
        self,
        chunk: bytes,
    ) -> SpeechStart | SpeechSegment | None:

        queued_event = (
            self.events.popleft()
            if self.events
            else None
        )

        self.frame_buffer.extend(chunk)

        while len(self.frame_buffer) >= self.FRAME_BYTES:

            frame = bytes(
                self.frame_buffer[: self.FRAME_BYTES]
            )

            del self.frame_buffer[: self.FRAME_BYTES]

            event = self.engine.process(frame)

            #
            # Collect audio while speech is active.
            #
            if self.collecting:

                self.segment_buffer.extend(frame)

                if (
                    len(self.segment_buffer)
                    >= self.MAX_SEGMENT_BYTES
                ):

                    audio = bytes(self.segment_buffer)

                    self.reset()

                    self.events.append(
                        SpeechSegment(audio)
                    )

                    break

            if event is None:
                continue

            #
            # Speech started.
            #
            if "start" in event:

                print("[VAD] Speech started")

                self.collecting = True

                self.segment_buffer.clear()
                self.segment_buffer.extend(frame)

                self.last_voice = monotonic()

                if not self.start_emitted:

                    self.start_emitted = True

                    self.events.append(
                        SpeechStart()
                    )

                continue

            #
            # Speech ended.
            #
            if "end" in event:

                print("[VAD] Speech ended")

                audio = bytes(self.segment_buffer)

                self.reset()

                if len(audio) >= self.MIN_SEGMENT_BYTES:

                    self.events.append(
                        SpeechSegment(audio)
                    )

                break

        if queued_event is not None:
            return queued_event

        if self.events:
            return self.events.popleft()

        return None
