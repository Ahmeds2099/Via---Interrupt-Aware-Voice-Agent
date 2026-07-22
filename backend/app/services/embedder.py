# pyrefly: ignore [missing-import]
from threading import Lock


class EmbeddingService:

    _model = None
    _lock = Lock()

    def __init__(self):
        pass

    @classmethod
    def _get_model(cls):
        if cls._model is None:
            with cls._lock:
                if cls._model is None:
                    from fastembed import TextEmbedding
                    cls._model = TextEmbedding(
                        model_name="BAAI/bge-small-en-v1.5"
                    )
        return cls._model

    def embed(
        self,
        texts: list[str],
    ) -> list[list[float]]:

        vectors = list(self._get_model().embed(texts))

        return [
            vector.tolist()
            for vector in vectors
        ]

    def embed_query(
        self,
        query: str,
    ) -> list[float]:

        return self.embed([query])[0]
