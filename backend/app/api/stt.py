import os
import shutil
import tempfile
import asyncio

from fastapi import APIRouter, File, UploadFile

from app.services.stt import STTFactory

router = APIRouter(
    prefix="/stt",
    tags=["Speech To Text"],
)

@router.post("/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
):

    suffix = os.path.splitext(audio.filename)[1]

    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=suffix,
    ) as temp_file:

        shutil.copyfileobj(
            audio.file,
            temp_file,
        )

        temp_path = temp_file.name

    try:
        # The legacy file endpoint is another explicit Whisper entry point.
        # Keep it cold until the endpoint is actually called.
        provider = await asyncio.to_thread(STTFactory.get_provider)
        transcript = await asyncio.to_thread(provider.transcribe, temp_path)
    finally:
        os.remove(temp_path)

    return {
        "transcript": transcript,
    }
