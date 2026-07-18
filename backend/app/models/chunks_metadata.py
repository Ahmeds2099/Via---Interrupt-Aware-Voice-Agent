from pydantic import BaseModel


class ChunkMetadata(BaseModel):

    document_id: str

    filename: str

    page_number: int

    chunk_index: int

    total_chunks: int

    text: str

    embedding_model: str

    created_at: str