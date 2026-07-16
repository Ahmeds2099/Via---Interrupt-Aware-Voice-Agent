import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    APP_NAME = "Via Backend"
    VERSION = "0.1.0"

    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

    QDRANT_URL = os.getenv("QDRANT_URL", "")
    QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")

    UPSTASH_REDIS_URL = os.getenv("UPSTASH_REDIS_URL", "")
    UPSTASH_REDIS_TOKEN = os.getenv("UPSTASH_REDIS_TOKEN", "")

    LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY", "")

    SENTRY_DSN = os.getenv("SENTRY_DSN", "")

    VAPI_API_KEY = os.getenv("VAPI_API_KEY", "")

    HUME_API_KEY = os.getenv("HUME_API_KEY", "")


settings = Settings()