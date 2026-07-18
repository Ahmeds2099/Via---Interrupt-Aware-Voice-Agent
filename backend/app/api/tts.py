from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel

from app.services.tts import TTSFactory

router = APIRouter(
    prefix="/tts",
    tags=["Text To Speech"],
)


class TTSRequest(BaseModel):
    text: str


provider = TTSFactory.get_provider()


@router.post("/synthesize")
async def synthesize(
    request: TTSRequest,
):

    audio = provider.synthesize(
        request.text,
    )

    return Response(
        content=audio,
        media_type="audio/wav",
    )