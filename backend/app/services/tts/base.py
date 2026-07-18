from abc import ABC, abstractmethod


class BaseTTSProvider(ABC):

    @abstractmethod
    def synthesize(
        self,
        text: str,
    ) -> bytes:
        pass