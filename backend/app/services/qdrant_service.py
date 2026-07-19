from operator import index
from uuid import uuid4

# pyrefly: ignore [missing-import]
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.core.qdrant import client


class QdrantService:

    COLLECTION_NAME = "via_documents"
    
    @classmethod
    
    def initialize(cls):

        collections = client.get_collections()

        existing = [
            collection.name
            for collection in collections.collections
        ]

        if cls.COLLECTION_NAME in existing:
            return

        client.create_collection(
            collection_name=cls.COLLECTION_NAME,
            vectors_config=VectorParams(
                size=384,
                distance=Distance.COSINE,
            ),
        )

    @classmethod
    def search(
        cls,
        query_vector: list[float],
        limit: int = 5,
    ):

        results = client.query_points(
        collection_name=cls.COLLECTION_NAME,
        query=query_vector,
        limit=limit,
        with_payload=True,
    ).points

        return [
        {
            "score": result.score,
            "filename": result.payload["filename"],
            "text": result.payload["text"],
        }
        for result in results
    ]         

    @classmethod
    def store_embeddings(
    chunks,
    embeddings,
    filename,
    document_id,
    created_at,
):

        points = []

        for index, (chunk, embedding) in enumerate(zip(chunks, embeddings)):

            points.append(
                PointStruct(
                    id=str(uuid4()),
                    vector=embedding,
                    payload = {
                    "document_id": document_id,
                    "filename": filename,
                    "page_number": 1,
                    "chunk_index": index,
                    "total_chunks": len(chunks),
                    "text": chunk,
                    "embedding_model": "BAAI/bge-small-en-v1.5",
                    "created_at": created_at,
}
                )
            )

        client.upsert(
            collection_name=cls.COLLECTION_NAME,
            points=points,
        )