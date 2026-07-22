import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    APP_NAME = "Via Backend"
    VERSION = "0.1.0"

    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

    CORS_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        ).split(",")
        if origin.strip()
    ]

    CORS_ORIGIN_REGEX: str | None = os.getenv(
        "CORS_ORIGIN_REGEX",
        (
            r"^https?://(?:localhost|127\.0\.0\.1|"
            r"10(?:\.\d{1,3}){3}|"
            r"192\.168(?:\.\d{1,3}){2}|"
            r"172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})"
            r"(?::\d+)?$"
            if ENVIRONMENT == "development"
            else ""
        ),
    ) or None

    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

    QDRANT_URL = os.getenv("QDRANT_URL", "")
    QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")

    UPSTASH_REDIS_URL = os.getenv("UPSTASH_REDIS_URL", "")
    UPSTASH_REDIS_TOKEN = os.getenv("UPSTASH_REDIS_TOKEN", "")

    UPSTASH_REDIS_REST_URL = os.getenv(
        "UPSTASH_REDIS_REST_URL",
        UPSTASH_REDIS_URL,
    )
    UPSTASH_REDIS_REST_TOKEN = os.getenv(
        "UPSTASH_REDIS_REST_TOKEN",
        UPSTASH_REDIS_TOKEN,
    )

    RAG_RELEVANCE_THRESHOLD: float = float(os.getenv(
        "RAG_RELEVANCE_THRESHOLD",
        "0.55",
    ))

    LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY", "")

    SENTRY_DSN = os.getenv("SENTRY_DSN", "")

    CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY", "")

    CARTESIA_VOICE_ID = os.getenv("CARTESIA_VOICE_ID", "")

    VOICE_SAMPLE_RATE: int = 16000

    VOICE_CHUNK_SIZE: int = 1024

    VOICE_ENABLE_STREAMING: bool = True

    VOICE_ENABLE_INTERRUPTION: bool = True

    WHISPER_MODEL: str = "base"

    WHISPER_DEVICE: str = "cpu"

    WHISPER_COMPUTE_TYPE: str = "int8"

    VOICE_STT_PROVIDER: str = os.getenv(
        "VOICE_STT_PROVIDER",
        "deepgram",
    ).strip().lower()

    VOICE_ALLOW_WHISPER_FALLBACK: bool = os.getenv(
        "VOICE_ALLOW_WHISPER_FALLBACK",
        "true",
    ).strip().lower() in {"1", "true", "yes", "on"}

    DEEPGRAM_API_KEY: str = os.getenv(
        "DEEPGRAM_API_KEY",
        "",
    )

    DEEPGRAM_MODEL: str = os.getenv(
        "DEEPGRAM_MODEL",
        "nova-2",
    )

    DEEPGRAM_LANGUAGE: str = os.getenv(
        "DEEPGRAM_LANGUAGE",
        "en-US",
    )

    DEEPGRAM_ENDPOINTING_MS: int = int(os.getenv(
        "DEEPGRAM_ENDPOINTING_MS",
        "300",
    ))

    DEEPGRAM_UTTERANCE_END_MS: int = int(os.getenv(
        "DEEPGRAM_UTTERANCE_END_MS",
        "1000",
    ))

    DEEPGRAM_KEYWORDS: str = os.getenv(
        "DEEPGRAM_KEYWORDS",
        "Via:3,Vee-ah:2,Vee-uh:2",
    )

    VOICE_MAX_TOKENS: int = int(os.getenv(
        "VOICE_MAX_TOKENS",
        "220",
    ))

    VOICE_INTERRUPTION_CONFIRM_TIMEOUT_SECONDS: float = float(os.getenv(
        "VOICE_INTERRUPTION_CONFIRM_TIMEOUT_SECONDS",
        "2.5",
    ))

    VOICE_ENABLE_EMOTION: bool = os.getenv(
        "VOICE_ENABLE_EMOTION",
        "true",
    ).strip().lower() in {"1", "true", "yes", "on"}

    EMOTION_DOUBT_THRESHOLD: float = float(os.getenv(
        "EMOTION_DOUBT_THRESHOLD",
        "0.70",
    ))

    EMOTION2VEC_MODEL: str = os.getenv(
        "EMOTION2VEC_MODEL",
        "iic/emotion2vec_plus_base",
    )

    EMOTION2VEC_HUB: str = os.getenv(
        "EMOTION2VEC_HUB",
        "hf",
    )

    EMOTION_WAIT_TIMEOUT_SECONDS: float = float(os.getenv(
        "EMOTION_WAIT_TIMEOUT_SECONDS",
        "0.30",
    ))

settings = Settings()
