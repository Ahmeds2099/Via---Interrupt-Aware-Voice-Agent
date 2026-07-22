from fastapi.middleware.cors import CORSMiddleware
from app.middleware.exception import generic_exception_handler
from fastapi import FastAPI
from app.api.upload import router as upload_router
from app.api.search import router as search_router
from app.api.stt import router as stt_router

from app.services.qdrant_service import QdrantService
from app.core.config import settings
from app.api.health import router as health_router
from fastapi.middleware.cors import CORSMiddleware
from app.middleware.exception import generic_exception_handler
from fastapi import FastAPI
from app.api.upload import router as upload_router
from app.api.search import router as search_router
from app.api.stt import router as stt_router

from app.services.qdrant_service import QdrantService
from app.core.config import settings
from app.api.health import router as health_router
from app.api.system import router as system_router
from app.api.ask import router as ask_router
from app.api.stream import router as stream_router
from app.api.tts import router as tts_router
from app.api import voice

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
)

@app.on_event("startup")
async def startup_event():
    try:
        import psutil
        import os
        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / 1024 / 1024
        print(f"[MEMORY] Startup Memory usage: {memory_mb:.2f} MB")
    except ImportError:
        print("[MEMORY] psutil not installed, skipping memory logging")

try:
    QdrantService.initialize()
except Exception:
    # Document retrieval is an enhancement, not a prerequisite for
    # starting Via in general voice-assistant mode. Runtime health is
    # reported by /system/status and ingestion returns an actionable 503.
    pass

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX,
    allow_private_network=(settings.ENVIRONMENT == "development"),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(
    Exception,
    generic_exception_handler,
)

app.include_router(health_router)
app.include_router(system_router)
app.include_router(upload_router)
app.include_router(search_router)
app.include_router(ask_router)
app.include_router(stream_router)
app.include_router(stt_router)
app.include_router(tts_router)
app.include_router(voice.router)

@app.get("/")
async def root():
    return {
        "message": "Via Backend Running"
    }
