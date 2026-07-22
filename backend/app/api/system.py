import asyncio

from fastapi import APIRouter

from app.core.config import settings
from app.core.qdrant import client
from app.services.emotion import emotion_provider
from app.services.session_repository import session_repository


router = APIRouter(prefix="/system", tags=["System"])


@router.get("/status")
async def system_status():
    redis_ready, qdrant_ready = await asyncio.gather(
        asyncio.to_thread(session_repository.ping),
        asyncio.to_thread(_qdrant_ready),
    )
    return {
        "app": settings.APP_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "status": "running",
        "providers": {
            "deepgram": "configured" if settings.DEEPGRAM_API_KEY else "missing",
            "groq": "configured" if settings.GROQ_API_KEY else "missing",
            "cartesia": "configured" if settings.CARTESIA_API_KEY else "missing",
            "qdrant": "ready" if qdrant_ready else "unavailable",
            "redis": session_repository.status,
            "emotion": emotion_provider.status,
        },
        "persistence": "ready" if redis_ready else "degraded",
    }


def _qdrant_ready() -> bool:
    try:
        client.get_collections()
        return True
    except Exception:
        return False
