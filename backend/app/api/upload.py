from pydantic import functional_serializers
from pathlib import Path
from uuid import uuid4
from app.services.embedder import EmbeddingService
from app.services.qdrant_service import QdrantService
from app.services.pdf_extractor import PDFExtractor
from fastapi import APIRouter, File, HTTPException, UploadFile
from app.services.chunker import TextChunker
from app.services.embedder import EmbeddingService
from datetime import datetime


created_at = datetime.utcnow().isoformat()

router = APIRouter(
    prefix="/upload",
    tags=["Upload"],
)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@router.post("/")
async def upload_document(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported.",
        )

    filename = f"{uuid4()}_{file.filename}"
    
    import uuid
    document_id = str(uuid.uuid4())
    destination = UPLOAD_DIR / filename

    with destination.open("wb") as buffer:
        buffer.write(await file.read())

    text = PDFExtractor.extract_text(str(destination))
    
    chunker = TextChunker()

    chunks = chunker.chunk(text)

    embedding_service = EmbeddingService()

    embeddings = embedding_service.embed(chunks)

    QdrantService.store_embeddings(
        filename=filename,
        chunks=chunks,
        embeddings=embeddings,
    )

    return {
    "success": True,
    "filename": filename,
    "original_filename": file.filename,
    "characters": len(text),
    "chunks": len(chunks),
    "stored_vectors": len(embeddings),
}