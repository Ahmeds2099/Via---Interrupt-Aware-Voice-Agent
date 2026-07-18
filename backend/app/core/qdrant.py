# pyrefly: ignore [missing-import]
from qdrant_client import QdrantClient

from app.core.config import settings

client = QdrantClient(
    url=settings.QDRANT_URL,
    api_key=settings.QDRANT_API_KEY,
)