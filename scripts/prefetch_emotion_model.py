"""Download and validate Via's local emotion2vec+ model before a demo."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.emotion import emotion_provider  # noqa: E402


if __name__ == "__main__":
    loaded = emotion_provider.load()
    print(emotion_provider.status)
    raise SystemExit(0 if loaded else 1)
