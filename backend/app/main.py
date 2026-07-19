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

QdrantService.initialize()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
    ],
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