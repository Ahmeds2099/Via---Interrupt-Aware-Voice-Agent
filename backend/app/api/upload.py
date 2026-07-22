from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.document_ingestion import DocumentIngestionService
from app.services.domain_classifier import DomainClassifier
from app.services.embedder import EmbeddingService
from app.services.qdrant_service import QdrantService


router = APIRouter(prefix="/upload", tags=["Upload"])

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
DEMO_DIR = Path(__file__).resolve().parents[3] / "docs" / "demo-data"

DEMO_DOCUMENTS = {
    "real-estate-brief": {
        "filename": "real-estate-brief.pdf",
        "title": "Real estate advisor",
        "description": "A concise property-market brief for a grounded advisor demo.",
        "format": "PDF",
    },
    "property-listings": {
        "filename": "property-listings.csv",
        "title": "Property listings analyst",
        "description": "Structured listings for comparison and recommendation questions.",
        "format": "CSV",
    },
    "development-details": {
        "filename": "development-details.json",
        "title": "Development specialist",
        "description": "Project details that demonstrate JSON-grounded role adaptation.",
        "format": "JSON",
    },
}

ingestion = DocumentIngestionService()
embedder = EmbeddingService()
domain_classifier = DomainClassifier()


def _ingest_contents(
    original_filename: str,
    contents: bytes,
    *,
    document_id: str | None = None,
) -> dict:
    extension = Path(original_filename).suffix.lower()
    if extension not in ingestion.SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Only PDF, CSV, and JSON files are supported.",
        )
    if len(contents) > ingestion.MAX_FILE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="The uploaded file exceeds the 10 MB limit.",
        )

    document_id = document_id or str(uuid4())
    stored_filename = f"{document_id}_{original_filename}"
    destination = UPLOAD_DIR / stored_filename
    destination.write_bytes(contents)

    try:
        source_type, chunks = ingestion.prepare(
            destination,
            original_filename,
        )
        sample = "\n".join(chunk.text for chunk in chunks[:20])
        domain = domain_classifier.classify(original_filename, sample)
        embeddings = embedder.embed([chunk.text for chunk in chunks])
        created_at = datetime.now(timezone.utc).isoformat()

        # Demo IDs are deterministic. Replacing their prior vectors keeps
        # repeated one-click demos from polluting the collection.
        QdrantService.delete_document(document_id)
        QdrantService.store_embeddings(
            document_id=document_id,
            filename=original_filename,
            chunks=[chunk.to_payload() for chunk in chunks],
            embeddings=embeddings,
            domain_profile=domain.to_dict(),
            created_at=created_at,
        )
    except ValueError as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        destination.unlink(missing_ok=True)
        raise
    except Exception as exc:
        destination.unlink(missing_ok=True)
        QdrantService.delete_document(document_id)
        raise HTTPException(
            status_code=503,
            detail=(
                "Document ingestion is temporarily unavailable. "
                "You can continue using Via without a document. "
                f"Details: {exc}"
            ),
        ) from exc

    locations = {
        (chunk.location_type, chunk.location_value)
        for chunk in chunks
    }
    return {
        "success": True,
        "document_id": document_id,
        "filename": original_filename,
        "source_type": source_type,
        "source_records": len(locations),
        "chunks": len(chunks),
        "stored_vectors": len(embeddings),
        "domain_profile": domain.to_dict(),
        "created_at": created_at,
    }


@router.post("/")
async def upload_document(file: UploadFile = File(...)):
    original_filename = Path(file.filename or "upload").name
    extension = Path(original_filename).suffix.lower()
    if extension not in ingestion.SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Only PDF, CSV, and JSON files are supported.",
        )

    allowed_content_types = {
        ".pdf": {"application/pdf", "application/octet-stream"},
        ".csv": {"text/csv", "application/csv", "application/vnd.ms-excel", "application/octet-stream"},
        ".json": {"application/json", "text/json", "application/octet-stream"},
    }
    if file.content_type and file.content_type not in allowed_content_types[extension]:
        raise HTTPException(
            status_code=400,
            detail="The file content type does not match its extension.",
        )

    contents = await file.read(ingestion.MAX_FILE_BYTES + 1)
    return _ingest_contents(original_filename, contents)


@router.get("/demos")
async def list_demo_documents():
    return {
        "documents": [
            {"slug": slug, **metadata}
            for slug, metadata in DEMO_DOCUMENTS.items()
        ]
    }


@router.post("/demos/{slug}")
async def activate_demo_document(slug: str):
    metadata = DEMO_DOCUMENTS.get(slug)
    if metadata is None:
        raise HTTPException(status_code=404, detail="Unknown demo document.")

    source = DEMO_DIR / metadata["filename"]
    if not source.is_file():
        raise HTTPException(
            status_code=503,
            detail="This demo document is not available in the deployment.",
        )

    contents = source.read_bytes()
    digest = hashlib.sha256(contents).hexdigest()
    document_id = str(uuid5(NAMESPACE_URL, f"via-demo:{slug}:{digest}"))
    result = _ingest_contents(
        metadata["filename"],
        contents,
        document_id=document_id,
    )
    return {**result, "demo_slug": slug}
