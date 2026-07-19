from __future__ import annotations

# pyrefly: ignore [missing-import]
import torch

# pyrefly: ignore [missing-import]
from silero_vad import (
    VADIterator,
    load_silero_vad,
)


class SileroEngine:

    SAMPLE_RATE = 16000
    FRAME_SAMPLES = 512
    FRAME_BYTES = FRAME_SAMPLES * 2

    def __init__(self):

        self.model = load_silero_vad()

        self.iterator = VADIterator(
            self.model,
            threshold=0.40,
            sampling_rate=self.SAMPLE_RATE,
            min_silence_duration_ms=700,
            speech_pad_ms=300,
        )

    def reset(self):
        self.iterator.reset_states()

    def process(self, pcm16: bytes):

        tensor = (
            torch.frombuffer(
                bytearray(pcm16),   # removes warning
                dtype=torch.int16,
            )
            .float()
            / 32768.0
        )

        return self.iterator(tensor)