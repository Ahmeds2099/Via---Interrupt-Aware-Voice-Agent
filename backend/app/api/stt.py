import os
import shutil
import tempfile

from fastapi import APIRouter, File, UploadFile

from app.services.stt import STTFactory

router = APIRouter(
    prefix="/stt",
    tags=["Speech To Text"],
)

provider = STTFactory.get_provider()


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

    transcript = provider.transcribe(
        temp_path,
    )

    os.remove(temp_path)

    return {
        "transcript": transcript,
    }