from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import uuid

from app.core.prompts import SYSTEM_PROMPT
from app.models.query import QueryRequest
from app.services.conversation_service import ConversationService
from app.services.embedder import EmbeddingService
from app.services.llm import LLMService
from app.services.prompt_builder import PromptBuilder
from app.services.qdrant_service import QdrantService

router = APIRouter(
    prefix="/stream",
    tags=["Streaming"],
)

embedder = EmbeddingService()
llm = LLMService()


@router.post("/")
def stream_answer(request: QueryRequest):

    session_id = request.session_id or str(uuid.uuid4())

    query_vector = embedder.embed_query(request.query)

    chunks = QdrantService.search(
        query_vector,
        document_ids=request.document_ids,
    )

    prompt = PromptBuilder.build(
        request.query,
        chunks,
    )

    history = ConversationService.get_messages(session_id)

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }
    ]

    for message in history:

        messages.append(
            {
                "role": message.role,
                "content": message.content,
            }
        )

    messages.append(
        {
            "role": "user",
            "content": prompt,
        }
    )

    def event_stream():

        complete_answer = ""

        for token in llm.stream(messages):

            complete_answer += token

            yield token

        ConversationService.add_message(
            session_id,
            "user",
            request.query,
        )

        ConversationService.add_message(
            session_id,
            "assistant",
            complete_answer,
        )

    return StreamingResponse(
        event_stream(),
        media_type="text/plain",
    )
