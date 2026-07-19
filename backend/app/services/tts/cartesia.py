from cartesia import Cartesia
import base64

from app.core.config import settings
from app.services.conversation.response_controller import (
    ResponseController,
)
from app.services.tts.base import BaseTTSProvider


class CartesiaProvider(BaseTTSProvider):

    def __init__(self):

        self.client = Cartesia(
            api_key=settings.CARTESIA_API_KEY,
        )

        self.controller: ResponseController | None = None

    def attach(
        self,
        controller: ResponseController,
    ):

        self.controller = controller

    def detach(self):

        self.controller = None

    def cancelled(self):

        return (
            self.controller is not None
            and self.controller.cancelled
        )

    def synthesize(
        self,
        text: str,
    ) -> bytes:

        response = self.client.tts.generate(
            model_id="sonic-3.5",
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

    def stream(
        self,
        text: str,
    ):

        if self.cancelled():
            return

        with self.client.tts.websocket_connect() as connection:

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

            ctx.push(text)

            ctx.no_more_inputs()

            try:

                for response in ctx.receive():

                    #
                    # Immediate interruption.
                    #
                    if self.cancelled():

                        print(
                            "[CARTESIA] Stream cancelled"
                        )

                        try:
                            ctx.no_more_inputs()
                        except Exception:
                            pass

                        return

                    response_type = getattr(
                        response,
                        "type",
                        None,
                    )

                    if response_type == "chunk":

                        audio = getattr(
                            response,
                            "data",
                            None,
                        )

                        if audio:

                            if isinstance(
                                audio,
                                str,
                            ):
                                audio = (
                                    base64.b64decode(audio)
                                )

                            yield audio

                    elif response_type == "done":

                        break

                    elif response_type == "error":

                        print(
                            "[CARTESIA] Error"
                        )

                        return

            finally:

                try:
                    connection.close()
                except Exception:
                    pass