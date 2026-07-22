from __future__ import annotations

import re
import tempfile
import wave
from dataclasses import asdict, dataclass
from dataclasses import replace
from pathlib import Path
from threading import Lock
from time import perf_counter

from app.core.config import settings


@dataclass(frozen=True, slots=True)
class EmotionResult:
    label: str = "unknown"
    raw_label: str = "unknown"
    display_label: str = "neutral"
    confidence: float = 0.0
    smoothed_confidence: float = 0.0
    reliable: bool = False
    scores: dict[str, float] | None = None
    provider: str = "emotion2vec+"
    processing_ms: float = 0.0
    doubt_score: float = 0.0
    clarification_mode: bool = False
    status: str = "unavailable"
    message: str = ""

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["scores"] = self.scores or {}
        return payload


class Emotion2VecProvider:
    """Lazy, failure-safe local speech emotion recognition."""

    UNCERTAINTY = re.compile(
        r"\b(confused|confusing|don't understand|do not understand|"
        r"not clear|what do you mean|lost|unsure|uncertain)\b",
        re.IGNORECASE,
    )
    STRESS_LABELS = {"angry", "sad", "fearful", "fear", "disgusted", "disgust"}
    UNDERSTANDING = re.compile(
        r"\b(okay|ok|got it|i understand|i get it|understood|makes sense|"
        r"that makes sense|all clear)\b",
        re.IGNORECASE,
    )
    RELIABLE_CONFIDENCE = 0.62
    STRESS_CONFIDENCE = 0.72

    def __init__(self) -> None:
        self.model = None
        self._lock = Lock()
        self._status = "disabled" if not settings.VOICE_ENABLE_EMOTION else "idle"
        self._message = ""

    @property
    def status(self) -> dict:
        return {
            "provider": "emotion2vec+",
            "status": self._status,
            "model": settings.EMOTION2VEC_MODEL,
            "message": self._message,
        }

    def load(self) -> bool:
        if not settings.VOICE_ENABLE_EMOTION:
            return False
        if self.model is not None:
            return True

        with self._lock:
            if self.model is not None:
                return True
            self._status = "loading"
            try:
                from funasr import AutoModel

                self.model = AutoModel(
                    model=settings.EMOTION2VEC_MODEL,
                    hub=settings.EMOTION2VEC_HUB,
                    disable_update=True,
                )
                self._status = "ready"
                self._message = ""
                return True
            except Exception as exc:
                self._status = "unavailable"
                self._message = f"Emotion model unavailable: {exc}"
                return False

    def analyze(
        self,
        pcm16_audio: bytes,
        transcript: str = "",
        stt_confidence: float | None = None,
    ) -> EmotionResult:
        started = perf_counter()
        if not self.load():
            return EmotionResult(
                status=self._status,
                message=self._message,
                processing_ms=(perf_counter() - started) * 1000,
            )

        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                suffix=".wav",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)

            with wave.open(str(temporary_path), "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(16000)
                wav_file.writeframes(pcm16_audio)

            with self._lock:
                raw = self.model.generate(
                    str(temporary_path),
                    granularity="utterance",
                    extract_embedding=False,
                )
            labels, scores = self._parse_result(raw)
            score_map = {
                self._normalize_label(label): float(score)
                for label, score in zip(labels, scores)
            }
            label = max(score_map, key=score_map.get) if score_map else "unknown"
            confidence = score_map.get(label, 0.0)
            reliable = confidence >= self.RELIABLE_CONFIDENCE
            display_label = self._display_label(label, reliable)
            doubt_score = self.derive_doubt(
                transcript,
                stt_confidence,
                label,
                confidence,
            )
            return EmotionResult(
                label=label,
                raw_label=label,
                display_label=display_label,
                confidence=confidence,
                smoothed_confidence=confidence if reliable else 0.0,
                reliable=reliable,
                scores=score_map,
                processing_ms=(perf_counter() - started) * 1000,
                doubt_score=doubt_score,
                clarification_mode=(
                    doubt_score >= settings.EMOTION_DOUBT_THRESHOLD
                ),
                status="ready",
            )
        except Exception as exc:
            self._status = "degraded"
            self._message = f"Emotion inference failed: {exc}"
            return EmotionResult(
                status="degraded",
                message=self._message,
                processing_ms=(perf_counter() - started) * 1000,
            )
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def enrich(
        self,
        result: EmotionResult,
        transcript: str,
        stt_confidence: float | None,
    ) -> EmotionResult:
        doubt_score = self.derive_doubt(
            transcript,
            stt_confidence,
            result.label,
            result.confidence,
        )
        explicit_understanding = bool(
            self.UNDERSTANDING.search(transcript)
            and not self.UNCERTAINTY.search(transcript)
        )
        return replace(
            result,
            doubt_score=doubt_score,
            display_label=(
                "neutral" if explicit_understanding
                else result.display_label
            ),
            reliable=(False if explicit_understanding else result.reliable),
            clarification_mode=(
                doubt_score >= settings.EMOTION_DOUBT_THRESHOLD
            ),
        )

    def smooth(
        self,
        result: EmotionResult,
        history: list[dict],
    ) -> tuple[EmotionResult, list[dict]]:
        """Smooth reliable observations without leaking state across users."""
        observations = list(history[-2:])
        if result.reliable:
            observations.append({
                "label": result.display_label,
                "confidence": result.confidence,
            })

        if not observations:
            return replace(
                result,
                display_label="neutral",
                smoothed_confidence=0.0,
                reliable=False,
            ), []

        weights: dict[str, float] = {}
        for observation in observations:
            label = str(observation.get("label", "neutral"))
            weights[label] = weights.get(label, 0.0) + float(
                observation.get("confidence", 0.0)
            )
        display_label = max(weights, key=weights.get)
        matching = [
            float(item.get("confidence", 0.0))
            for item in observations
            if item.get("label") == display_label
        ]
        smoothed = sum(matching) / max(1, len(matching))

        stress_count = sum(
            1 for item in observations if item.get("label") == "stressed"
        )
        doubt = result.doubt_score
        if display_label == "stressed" and stress_count >= 2:
            doubt = max(doubt, smoothed * 0.75)

        return replace(
            result,
            display_label=display_label,
            smoothed_confidence=smoothed,
            reliable=result.reliable,
            doubt_score=doubt,
            clarification_mode=(
                doubt >= settings.EMOTION_DOUBT_THRESHOLD
            ),
        ), observations[-3:]

    @staticmethod
    def _parse_result(raw) -> tuple[list, list]:
        item = raw[0] if isinstance(raw, list) and raw else raw
        if not isinstance(item, dict):
            return [], []
        return list(item.get("labels") or []), list(item.get("scores") or [])

    @staticmethod
    def _normalize_label(label: str) -> str:
        normalized = str(label).strip().lower()
        normalized = normalized.strip("/<>| _")
        if "/" in normalized:
            normalized = normalized.rsplit("/", 1)[-1]
        return normalized or "unknown"

    @classmethod
    def _display_label(cls, label: str, reliable: bool) -> str:
        if not reliable:
            return "neutral"
        if label in cls.STRESS_LABELS:
            return "stressed"
        if label in {"confused", "uncertain"}:
            return "confused" if label == "confused" else "uncertain"
        return "neutral"

    @classmethod
    def derive_doubt(
        cls,
        transcript: str,
        stt_confidence: float | None,
        label: str,
        confidence: float,
    ) -> float:
        score = 0.0
        if cls.UNCERTAINTY.search(transcript):
            score = max(score, 0.85)
        elif cls.UNDERSTANDING.search(transcript):
            return 0.0
        if label in cls.STRESS_LABELS and confidence >= cls.STRESS_CONFIDENCE:
            score = max(score, confidence * 0.8)
        if stt_confidence is not None and stt_confidence < 0.65:
            score = max(score, 0.55 + (0.65 - stt_confidence))
        return max(0.0, min(1.0, score))
