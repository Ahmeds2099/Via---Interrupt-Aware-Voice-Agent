from fastapi import APIRouter
from app.core.config import settings

router = APIRouter(prefix="/system", tags=["System"])


@router.get("/status")
async def system_status():
    return {
        "app": settings.APP_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "status": "running"
    }