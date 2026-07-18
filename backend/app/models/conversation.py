from pydantic import BaseModel
from typing import Optional

class Message(BaseModel):
    role: str
    content: str


class Conversation(BaseModel):
    session_id: str
    messages: list[Message]

class AskRequest(BaseModel):
    query: str
    session_id: Optional[str] = None