from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
async def health():
    return {
        "status": "ok",
        "service": "Via Backend",
        "version": "0.1.0",
    }