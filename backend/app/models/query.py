from typing import Optional
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    client_id: Optional[str] = None
    document_ids: list[str] = Field(default_factory=list)
