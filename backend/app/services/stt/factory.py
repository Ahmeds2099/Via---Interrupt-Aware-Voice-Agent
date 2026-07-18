from app.services.stt.whisper import WhisperProvider


class STTFactory:

    _provider = None

    @classmethod
    def get_provider(cls):

        if cls._provider is None:
            cls._provider = WhisperProvider()

        return cls._provider
        