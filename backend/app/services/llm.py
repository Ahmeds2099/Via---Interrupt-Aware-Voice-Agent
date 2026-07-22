# pyrefly: ignore [missing-import]
from groq import Groq
import json

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
        max_tokens: int | None = None,
    ):

        request = {
            "model": "llama-3.3-70b-versatile",
            "temperature": 0.2,
            "messages": messages,
            "stream": True,
        }

        if max_tokens is not None:
            request["max_tokens"] = max_tokens

        stream = self.client.chat.completions.create(
            **request,
        )

        for chunk in stream:

            delta = chunk.choices[0].delta.content

            if delta:
                yield delta

    def classify_interruption(self, transcript: str) -> dict | None:
        """Return a small JSON interruption decision for ambiguous turns."""
        response = self.client.chat.completions.create(
            model="llama-3.1-8b-instant",
            temperature=0,
            max_tokens=80,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Classify a voice interruption. Return JSON only with "
                        "intent and resume_policy. intent must be one of "
                        "stop, backchannel, clarification, side_question, "
                        "topic_switch, resume, decline, other. "
                        "resume_policy must be discard, automatic, confirm, "
                        "keep_paused, or none. Stop means cancel and discard. "
                        "A distinct question is side_question. A request to "
                        "explain the current answer is clarification."
                    ),
                },
                {"role": "user", "content": transcript},
            ],
        )
        content = response.choices[0].message.content or "{}"
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return None
