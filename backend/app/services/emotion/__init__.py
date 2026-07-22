from app.services.emotion.provider import (
    Emotion2VecProvider,
    EmotionResult,
)

emotion_provider = Emotion2VecProvider()

__all__ = ["Emotion2VecProvider", "EmotionResult", "emotion_provider"]
