"""Deterministic interruption semantics with an optional LLM fallback.

The voice path must remain useful when Groq is unavailable, so obvious phrases
are classified locally and only ambiguous paused-topic turns are delegated.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class InterruptionDecision:
    intent: str = "other"
    resume_policy: str = "none"
    confidence: float = 0.0
    source: str = "deterministic"


AFFIRMATIVE_MARKERS = (
    "yes", "yeah", "yep", "yup", "sure", "please", "go ahead",
    "go on", "continue", "carry on", "keep going", "sounds good",
    "okay", "ok", "alright", "all right",
)

NEGATIVE_MARKERS = (
    "no thanks", "no thank you", "that's fine", "thats fine",
    "that's okay", "thats okay", "that's all", "thats all",
    "never mind", "nevermind", "i'm good", "im good", "we're done",
    "were done", "that's enough", "thats enough", "nope", "nah",
)

BACKCHANNEL_MARKERS = (
    "okay", "ok", "got it", "i got it", "understood", "i understand",
    "i get it", "makes sense", "right", "uh huh", "mm hmm", "mm-hmm",
    "all right", "alright",
)

STOP_EXACT = {
    "stop", "stop now", "please stop", "cancel", "cancel that", "pause",
    "be quiet", "quiet", "that's enough", "thats enough", "enough",
    "don't continue", "do not continue", "never mind", "nevermind",
}

_BARE_NO = re.compile(r"\bno\b")
_CONTEXT_REQUESTS = (
    re.compile(r"^what (?:were we|were you) (?:saying|talking|discussing)(?: about)?(?: before| earlier)?$"),
    re.compile(r"^where were we(?: before| earlier)?$"),
    re.compile(r"^what was (?:the )?(?:original|previous) topic$"),
    re.compile(r"^remind me what (?:we|you) were (?:saying|talking|discussing)(?: about)?$"),
)
_CLARIFICATION = re.compile(
    r"\b(what do you mean|can you explain that|explain that|why is that|"
    r"how does that work|i'm confused|im confused|i don't understand|"
    r"i do not understand|not clear|say that again)\b",
    re.IGNORECASE,
)
_TOPIC_SWITCH = re.compile(
    r"\b(let's talk about|lets talk about|switch to|change the subject|"
    r"different topic|instead,|instead can|actually,? (?:tell|explain|what)|"
    r"i have another question)\b",
    re.IGNORECASE,
)
_QUESTION = re.compile(r"\b(who|what|when|where|why|how|can|could|would|is|are|do|does)\b", re.IGNORECASE)


def _normalize(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[.,!?]+$", "", text)
    return re.sub(r"\s+", " ", text).strip()


def classify_resume_intent(transcript: str) -> str:
    """Backward-compatible yes/no/other classifier for fallback consent."""
    normalized = _normalize(transcript)
    if not normalized or len(normalized.split()) > 6:
        return "other"
    if _BARE_NO.search(normalized) or any(marker in normalized for marker in NEGATIVE_MARKERS):
        return "no"
    if any(marker in normalized for marker in AFFIRMATIVE_MARKERS):
        return "yes"
    return "other"


def is_resume_context_request(transcript: str) -> bool:
    normalized = _normalize(transcript)
    return any(pattern.search(normalized) for pattern in _CONTEXT_REQUESTS)


def _deterministic(transcript: str, awaiting_resume: bool) -> InterruptionDecision | None:
    normalized = _normalize(transcript)
    if not normalized:
        return None
    words = normalized.split()

    if normalized in STOP_EXACT or (len(words) <= 4 and normalized.startswith("stop ")):
        return InterruptionDecision("stop", "discard", 1.0)
    if is_resume_context_request(normalized):
        return InterruptionDecision("other", "keep_paused", 1.0)

    if awaiting_resume and classify_resume_intent(normalized) == "yes":
        # Backchannels become explicit resume decisions only while Via is
        # waiting for a decision about a paused answer.
        return InterruptionDecision("resume", "automatic", 1.0)
    if awaiting_resume and classify_resume_intent(normalized) == "no":
        return InterruptionDecision("decline", "discard", 1.0)

    if len(words) <= 6 and normalized in BACKCHANNEL_MARKERS:
        return InterruptionDecision("backchannel", "automatic", 0.96)
    if _CLARIFICATION.search(normalized):
        return InterruptionDecision("clarification", "confirm", 0.9)
    if _TOPIC_SWITCH.search(normalized):
        return InterruptionDecision("topic_switch", "discard", 0.86)
    if _QUESTION.search(normalized) or normalized.endswith("?"):
        return InterruptionDecision("side_question", "automatic", 0.7)
    return None


def classify_interruption(
    transcript: str,
    *,
    awaiting_resume: bool = False,
    classifier: Callable[[str], str | dict | None] | None = None,
) -> InterruptionDecision:
    """Classify a paused-topic turn, safely falling back to local rules."""
    local = _deterministic(transcript, awaiting_resume)
    if local is not None:
        return local
    if classifier is not None:
        try:
            raw = classifier(transcript)
            payload = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(payload, dict):
                intent = str(payload.get("intent", "other")).strip().lower()
                policy = str(payload.get("resume_policy", "none")).strip().lower()
                allowed_intents = {"stop", "backchannel", "clarification", "side_question", "topic_switch", "resume", "decline", "other"}
                allowed_policies = {"discard", "automatic", "confirm", "keep_paused", "none"}
                if intent in allowed_intents and policy in allowed_policies:
                    return InterruptionDecision(intent, policy, float(payload.get("confidence", 0.55)), "groq")
        except Exception:
            # Rate limits, malformed JSON, and provider outages must never
            # break the local interruption state machine.
            pass
    # A question is safer as an independent side question than as a forced
    # clarification. The original answer remains paused for automatic return.
    return InterruptionDecision("side_question", "automatic", 0.35, "fallback")
