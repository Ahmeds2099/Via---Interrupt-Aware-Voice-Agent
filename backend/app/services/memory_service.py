from __future__ import annotations

from uuid import uuid4

# pyrefly: ignore [missing-import]
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from app.core.qdrant import client
from app.services.conversation_service import ConversationService
from app.services.embedder import EmbeddingService
from app.services.session_repository import session_repository


class MemoryService:
    COLLECTION_NAME = "via_memories"

    def __init__(self) -> None:
        self.embedder = EmbeddingService()
        self.initialize()

    def initialize(self) -> None:
        try:
            collections = client.get_collections()
            existing = {collection.name for collection in collections.collections}
            if self.COLLECTION_NAME not in existing:
                client.create_collection(
                    collection_name=self.COLLECTION_NAME,
                    vectors_config=VectorParams(size=384, distance=Distance.COSINE),
                )
            self._ensure_client_index()
        except Exception:
            # Redis-backed memories remain available when Qdrant is degraded.
            return

    def _ensure_client_index(self) -> None:
        client.create_payload_index(
            collection_name=self.COLLECTION_NAME,
            field_name="client_id",
            field_schema=PayloadSchemaType.KEYWORD,
            wait=True,
        )

    def store_memory(self, text: str, client_id: str) -> str:
        memory_id = str(uuid4())
        embedding = self.embedder.embed_query(text)
        ConversationService.add_memory(client_id, memory_id, text)
        try:
            client.upsert(
                collection_name=self.COLLECTION_NAME,
                points=[
                    PointStruct(
                        id=memory_id,
                        vector=embedding,
                        payload={
                            "memory_id": memory_id,
                            "client_id": client_id,
                            "text": text,
                        },
                    )
                ],
            )
        except Exception:
            # The durable Redis copy is sufficient for graceful fallback.
            pass
        return memory_id

    def search(
        self,
        query: str,
        client_id: str,
        limit: int = 3,
    ) -> list[str]:
        embedding = self.embedder.embed_query(query)
        def query_qdrant():
            return client.query_points(
                collection_name=self.COLLECTION_NAME,
                query=embedding,
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key="client_id",
                            match=MatchValue(value=client_id),
                        )
                    ]
                ),
                limit=limit,
                score_threshold=0.6,
                with_payload=True,
            ).points

        try:
            results = query_qdrant()
        except Exception as exc:
            message = str(exc).lower()
            if "index required" in message and "client_id" in message:
                try:
                    self._ensure_client_index()
                    results = query_qdrant()
                except Exception:
                    return self._fallback_memories(client_id, limit)
            else:
                return self._fallback_memories(client_id, limit)

        return [
            result.payload["text"]
            for result in results
            if result.payload and result.payload.get("text")
        ]

    @staticmethod
    def _fallback_memories(client_id: str, limit: int) -> list[str]:
        state = session_repository.load(client_id)
        memories = state.get("memories", [])
        return [
            item["text"]
            for item in memories[-limit:]
            if isinstance(item, dict) and item.get("text")
        ]
