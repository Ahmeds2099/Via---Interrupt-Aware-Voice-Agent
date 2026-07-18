from app.services.tts.cartesia import CartesiaProvider


class TTSFactory:

    _provider = None

    @classmethod
    def get_provider(cls):

        if cls._provider is None:
            cls._provider = CartesiaProvider()

        return cls._provider