from __future__ import annotations

from uuid import uuid4

from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    PayloadSchemaType,
    FilterSelector,
    PointStruct,
    VectorParams,
)

from app.core.config import settings
from app.core.qdrant import client


class QdrantService:
    COLLECTION_NAME = "via_documents"

    @classmethod
    def initialize(cls) -> None:
        collections = client.get_collections()
        existing = {collection.name for collection in collections.collections}
        if cls.COLLECTION_NAME not in existing:
            client.create_collection(
                collection_name=cls.COLLECTION_NAME,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )
        client.create_payload_index(
            collection_name=cls.COLLECTION_NAME,
            field_name="document_id",
            field_schema=PayloadSchemaType.KEYWORD,
            wait=True,
        )

    @classmethod
    def search(
        cls,
        query_vector: list[float],
        limit: int = 5,
        document_ids: list[str] | None = None,
        min_score: float | None = None,
    ) -> list[dict]:
        # An explicitly empty context means that the user chose general
        # assistant mode. It must never fall through to a collection-wide
        # search and leak context from unrelated uploads.
        if document_ids == []:
            return []

        query_filter = None
        if document_ids:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchAny(any=document_ids),
                    )
                ]
            )

        results = client.query_points(
            collection_name=cls.COLLECTION_NAME,
            query=query_vector,
            query_filter=query_filter,
            limit=limit,
            score_threshold=(
                settings.RAG_RELEVANCE_THRESHOLD
                if min_score is None
                else min_score
            ),
            with_payload=True,
        ).points

        matches = []
        for result in results:
            payload = result.payload or {}
            matches.append(
                {
                    "score": result.score,
                    "document_id": payload.get("document_id"),
                    "filename": payload.get("filename", "uploaded document"),
                    "text": payload.get("text", ""),
                    "source_type": payload.get("source_type"),
                    "location_type": payload.get("location_type"),
                    "location_value": payload.get("location_value"),
                    "domain_profile": payload.get("domain_profile") or {},
                }
            )
        return matches

    @classmethod
    def store_embeddings(
        cls,
        chunks: list[dict],
        embeddings: list[list[float]],
        filename: str,
        document_id: str,
        created_at: str,
        domain_profile: dict,
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("Chunk and embedding counts do not match.")

        cls.initialize()
        points = [
            PointStruct(
                id=str(uuid4()),
                vector=embedding,
                payload={
                    "document_id": document_id,
                    "filename": filename,
                    "source_type": chunk["source_type"],
                    "location_type": chunk["location_type"],
                    "location_value": chunk["location_value"],
                    "chunk_index": index,
                    "total_chunks": len(chunks),
                    "text": chunk["text"],
                    "domain_profile": domain_profile,
                    "embedding_model": "BAAI/bge-small-en-v1.5",
                    "created_at": created_at,
                },
            )
            for index, (chunk, embedding) in enumerate(zip(chunks, embeddings))
        ]
        client.upsert(collection_name=cls.COLLECTION_NAME, points=points)

    @classmethod
    def delete_document(cls, document_id: str) -> None:
        try:
            client.delete(
                collection_name=cls.COLLECTION_NAME,
                points_selector=FilterSelector(
                    filter=Filter(
                        must=[
                            FieldCondition(
                                key="document_id",
                                match=MatchValue(value=document_id),
                            )
                        ]
                    )
                ),
            )
        except Exception:
            pass
