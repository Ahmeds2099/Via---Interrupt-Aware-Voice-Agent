from fastapi import APIRouter

from app.models.query import QueryRequest
from app.services.conversation_manager import ConversationManager

router = APIRouter(
    prefix="/ask",
    tags=["RAG"],
)

manager = ConversationManager()


@router.post("/")
def ask(request: QueryRequest):
    session_id = request.session_id
    if session_id is None:
        from uuid import uuid4
        session_id = str(uuid4())
    return manager.chat(
        query=request.query,
        session_id=session_id,
        document_ids=request.document_ids,
        client_id=request.client_id,
    )
