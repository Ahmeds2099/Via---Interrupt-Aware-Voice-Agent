from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

from app.services.voice.silero import SileroEngine


@dataclass
class SpeechSegment:

    audio: bytes


class VoiceActivityDetector:

    FRAME_BYTES = 1024                 # 512 samples
    MAX_SEGMENT_SECONDS = 15
    SAMPLE_RATE = 16000
    SAMPLE_WIDTH = 2

    MAX_SEGMENT_BYTES = (
        MAX_SEGMENT_SECONDS
        * SAMPLE_RATE
        * SAMPLE_WIDTH
    )

    def __init__(self):

        self.engine = SileroEngine()

        self.frame_buffer = bytearray()

        self.segment_buffer = bytearray()

        self.collecting = False

        self.last_voice = monotonic()

    def reset(self):

        self.frame_buffer.clear()

        self.segment_buffer.clear()

        self.collecting = False

        self.last_voice = monotonic()

        self.engine.reset()

    def update(
        self,
        chunk: bytes,
    ) -> SpeechSegment | None:

        self.frame_buffer.extend(chunk)

        while len(self.frame_buffer) >= self.FRAME_BYTES:

            frame = bytes(
                self.frame_buffer[: self.FRAME_BYTES]
            )

            del self.frame_buffer[: self.FRAME_BYTES]

            event = self.engine.process(frame)

            #
            # Append audio while speech is active.
            #
            if self.collecting:

                self.segment_buffer.extend(frame)

                if (
                    len(self.segment_buffer)
                    >= self.MAX_SEGMENT_BYTES
                ):

                    audio = bytes(self.segment_buffer)

                    self.reset()

                    return SpeechSegment(audio)

            if event is None:
                continue

            #
            # Speech begins.
            #
            if "start" in event:

                print("[VAD] Speech started")

                self.collecting = True

                self.segment_buffer.clear()

                self.segment_buffer.extend(frame)

                self.last_voice = monotonic()

                continue

            #
            # Speech finished.
            #
            if "end" in event:

                print("[VAD] Speech ended")

                audio = bytes(self.segment_buffer)

                self.reset()

                MIN_SEGMENT_BYTES = 32000  # ≈1 second at 16 kHz PCM16

                if len(audio) < MIN_SEGMENT_BYTES:
                    return None

                return SpeechSegment(audio)

        return None