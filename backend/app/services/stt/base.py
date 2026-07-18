from abc import ABC, abstractmethod


class BaseSTTProvider(ABC):

    @abstractmethod
    def transcribe(
        self,
        audio_path: str,
    ) -> str:
        pass