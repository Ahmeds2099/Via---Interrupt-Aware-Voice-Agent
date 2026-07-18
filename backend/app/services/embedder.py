# pyrefly: ignore [missing-import]
from fastembed import TextEmbedding


class EmbeddingService:

    def __init__(self):
        self.model = TextEmbedding(
            model_name="BAAI/bge-small-en-v1.5"
        )

    def embed(
        self,
        texts: list[str],
    ) -> list[list[float]]:

        vectors = list(self.model.embed(texts))

        return [
            vector.tolist()
            for vector in vectors
        ]

    def embed_query(
        self,
        query: str,
    ) -> list[float]:

        return self.embed([query])[0]