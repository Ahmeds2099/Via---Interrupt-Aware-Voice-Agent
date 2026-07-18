# pyrefly: ignore [missing-import]
from groq import Groq

from app.core.config import settings
from app.core.prompts import SYSTEM_PROMPT


class LLMService:

    def __init__(self):

        self.client = Groq(
            api_key=settings.GROQ_API_KEY,
        )

    def generate(
        self,
        messages: list[dict],
    ) -> str:

        response = self.client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            temperature=0.2,
            messages=messages,
        )

        return response.choices[0].message.content

    def stream(
        self,
        messages: list[dict],
    ):

        stream = self.client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            temperature=0.2,
            messages=messages,
            stream=True,
        )

        for chunk in stream:

            delta = chunk.choices[0].delta.content

            if delta:
                yield delta