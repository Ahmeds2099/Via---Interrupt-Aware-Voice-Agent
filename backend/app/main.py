from fastapi.middleware.cors import CORSMiddleware
from app.middleware.exception import generic_exception_handler
from app.api import system
from fastapi import FastAPI

from app.core.config import settings
from app.api.health import router as health_router
from app.api.system import router as system_router


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
)
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

@app.get("/")
async def root():
    return {
        "message": "Via Backend Running"
    }