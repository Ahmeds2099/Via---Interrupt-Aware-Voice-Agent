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

    return manager.chat(
        query=request.query,
        session_id=request.session_id,
    )