from cartesia import Cartesia

from app.core.config import settings
from app.services.tts.base import BaseTTSProvider


class CartesiaProvider(BaseTTSProvider):
    def __init__(self):
        self.client = Cartesia(
            api_key=settings.CARTESIA_API_KEY,
        )

    def synthesize(self, text: str) -> bytes:
        response = self.client.tts.generate(
            model_id="sonic-2",
            transcript=text,
            voice={
                "mode": "id",
                "id": settings.CARTESIA_VOICE_ID,
            },
            output_format={
                "container": "wav",
                "encoding": "pcm_f32le",
                "sample_rate": 16000,
            },
        )

        return b"".join(response.iter_bytes())