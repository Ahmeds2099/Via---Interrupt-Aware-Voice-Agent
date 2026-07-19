from cartesia import Cartesia
from app.core.config import settings

client = Cartesia(api_key=settings.CARTESIA_API_KEY)

with client.tts.websocket_connect() as connection:

    ctx = connection.context(
        model_id="sonic-3.5",
        voice={
            "mode": "id",
            "id": settings.CARTESIA_VOICE_ID,
        },
        language="en",
        output_format={
            "container": "raw",
            "encoding": "pcm_f32le",
            "sample_rate": 16000,
        },
    )

    print(type(ctx))
    print(dir(ctx))