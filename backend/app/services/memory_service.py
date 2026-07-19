from __future__ import annotations

from uuid import uuid4

# pyrefly: ignore [missing-import]
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.core.qdrant import client
from app.services.embedder import EmbeddingService


class MemoryService:

    COLLECTION_NAME = "via_memories"

    def __init__(self):

        self.embedder = EmbeddingService()

        self.initialize()

    def initialize(self):

        collections = client.get_collections()

        existing = [
            c.name
            for c in collections.collections
        ]

        if self.COLLECTION_NAME in existing:
            return

        client.create_collection(
            collection_name=self.COLLECTION_NAME,
            vectors_config=VectorParams(
                size=384,
                distance=Distance.COSINE,
            ),
        )

    def store_memory(
        self,
        text: str,
    ):

        embedding = self.embedder.embed_query(text)

        client.upsert(
            collection_name=self.COLLECTION_NAME,
            points=[
                PointStruct(
                    id=str(uuid4()),
                    vector=embedding,
                    payload={
                        "text": text,
                    },
                )
            ],
        )

    def search(
        self,
        query: str,
        limit: int = 3,
    ):

        embedding = self.embedder.embed_query(query)

        results = client.query_points(
            collection_name=self.COLLECTION_NAME,
            query=embedding,
            limit=limit,
            with_payload=True,
        ).points

        return [
            r.payload["text"]
            for r in results
        ]