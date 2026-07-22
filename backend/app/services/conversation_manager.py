from __future__ import annotations

import uuid
from time import perf_counter
from uuid import uuid4

from app.core.config import settings
from app.core.prompts import (
    CLARIFICATION_MODE_PROMPT,
    SYSTEM_PROMPT,
    VOICE_RESPONSE_PROMPT,
)
from app.services.conversation.paused_response import PausedResponse
from app.services.conversation_service import ConversationService
from app.services.embedder import EmbeddingService
from app.services.llm import LLMService
from app.services.memory_extractor import MemoryExtractor
from app.services.memory_service import MemoryService
from app.services.prompt_builder import PromptBuilder
from app.services.qdrant_service import QdrantService
from app.services.tts.stream import StreamingTTS


class ConversationManager:
    def __init__(self):
        self.embedder = EmbeddingService()
        self.llm = LLMService()
        self.memory = MemoryService()

    def build_messages(
        self,
        query: str,
        session_id: str,
        voice_mode: bool = False,
        emotional_context: dict | None = None,
        document_ids: list[str] | None = None,
        client_id: str | None = None,
        interruption_context: dict | None = None,
    ) -> tuple[list[dict], list[dict], dict]:
        query_vector = self.embedder.embed_query(query)
        chunks = QdrantService.search(
            query_vector,
            document_ids=document_ids,
        )
        prompt = PromptBuilder.build(query, chunks)
        history = ConversationService.get_messages(session_id)
        memories = self.memory.search(
            query,
            client_id=client_id or session_id,
        )

        messages: list[dict] = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            }
        ]

        if voice_mode:
            messages.append(
                {
                    "role": "system",
                    "content": VOICE_RESPONSE_PROMPT,
                }
            )

            if not settings.VOICE_ENABLE_EMOTION and not settings.VOICE_ALLOW_WHISPER_FALLBACK:
                messages.append(
                    {
                        "role": "system",
                        "content": (
                            "IMPORTANT: You are running in a constrained demo environment. "
                            "Keep your responses extremely short. Limit all answers to 1 or 2 brief sentences maximum. "
                            "This ensures quick processing and allows the user to test barge-in functionality."
                        )
                    }
                )

        if (
            emotional_context
            and emotional_context.get("doubt_score", 0)
            >= settings.EMOTION_DOUBT_THRESHOLD
        ):
            messages.append(
                {
                    "role": "system",
                    "content": CLARIFICATION_MODE_PROMPT,
                }
            )

        if interruption_context:
            mode = interruption_context.get("mode")
            paused_topic = interruption_context.get("paused_topic", "")
            if mode == "clarification":
                messages.append({
                    "role": "system",
                    "content": (
                        "This turn is a clarification about a paused answer. "
                        "Answer the new question directly in simpler language. "
                        "End with one short, natural question about returning "
                        f"to the paused topic ({paused_topic}). Never say "
                        "'Does that clear things up?' and do not repeat the "
                        "paused topic as a filename."
                    ),
                })
            elif mode == "side_question":
                messages.append({
                    "role": "system",
                    "content": (
                        "Answer this independent side question directly. Do "
                        "not ask whether the user wants to resume; Via will "
                        "return to the paused answer automatically."
                    ),
                })

        if memories:
            memory_block = "\n".join(
                f"- {memory}" for memory in memories
            )
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "Known user information:\n" + memory_block
                    ),
                }
            )

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

        return messages, chunks, {
            "memory_count": len(memories),
            "document_count": len({
                chunk.get("document_id")
                for chunk in chunks
                if chunk.get("document_id")
            }),
        }

    def generate_response(
        self,
        query: str,
        session_id: str,
        document_ids: list[str] | None = None,
        client_id: str | None = None,
    ) -> dict:
        ConversationService.bind(
            session_id,
            client_id or session_id,
        )
        messages, chunks, _ = self.build_messages(
            query,
            session_id,
            document_ids=document_ids,
            client_id=client_id,
        )
        answer = self.llm.generate(messages)


        memory = MemoryExtractor.extract(query)
        if memory:
            self.memory.store_memory(
                memory,
                client_id=client_id or session_id,
            )

        ConversationService.add_message(session_id, "user", query)
        ConversationService.add_message(
            session_id,
            "assistant",
            answer,
        )

        return {
            "session_id": session_id,
            "question": query,
            "answer": answer,
            "chunks": chunks,
        }

    def chat(
        self,
        query: str,
        session_id: str | None = None,
        document_ids: list[str] | None = None,
        client_id: str | None = None,
    ) -> dict:
        if session_id is None:
            session_id = str(uuid.uuid4())
        return self.generate_response(
            query,
            session_id,
            document_ids=document_ids,
            client_id=client_id,
        )

    def stream_response(
        self,
        query: str,
        session_id: str,
    ):
        messages, _, _ = self.build_messages(query, session_id)
        accumulated = ""

        for token in self.llm.stream(messages):
            if token:
                accumulated += token
                yield token

        ConversationService.add_message(session_id, "user", query)
        ConversationService.add_message(
            session_id,
            "assistant",
            accumulated,
        )

    @staticmethod
    def _sentence_items(
        tts: StreamingTTS,
        response_id: str,
        sentence: str,
        end_offset: int,
        response: PausedResponse | None = None,
        turn_started: float | None = None,
    ):
        segment_id = str(uuid4())

        if response is not None:
            response.register_segment(segment_id, end_offset)

        yield {
            "type": "segment_start",
            "response_id": response_id,
            "data": {
                "response_id": response_id,
                "segment_id": segment_id,
                "text": sentence,
                "end_offset": end_offset,
            },
        }

        tts_started = perf_counter()
        first_audio = True
        for audio in tts.stream_sentence(sentence):
            if tts.cancelled():
                return
            if first_audio:
                first_audio = False
                now = perf_counter()
                yield {
                    "type": "pipeline_stage",
                    "response_id": response_id,
                    "data": {
                        "stage": "tts",
                        "status": "first_byte",
                        "duration_ms": round(
                            (now - tts_started) * 1000,
                        ),
                        "elapsed_ms": (
                            round((now - turn_started) * 1000)
                            if turn_started is not None
                            else None
                        ),
                    },
                }
            yield {
                "type": "audio",
                "response_id": response_id,
                "data": audio,
            }

        if not tts.cancelled():
            yield {
                "type": "segment_end",
                "response_id": response_id,
                "data": {
                    "response_id": response_id,
                    "segment_id": segment_id,
                },
            }

    def stream_voice(
        self,
        query: str,
        session_id: str,
        controller,
        conversation_state,
        emotional_context: dict | None = None,
        document_ids: list[str] | None = None,
        client_id: str | None = None,
        interruption_context: dict | None = None,
    ):
        if controller.response_id is None:
            controller.begin()

        response_id = controller.response_id
        turn_started = perf_counter()
        yield {
            "type": "pipeline_stage",
            "response_id": response_id,
            "data": {
                "stage": "retrieval",
                "status": "active",
                "elapsed_ms": 0,
            },
        }
        retrieval_started = perf_counter()
        messages, chunks, context = self.build_messages(
            query,
            session_id,
            voice_mode=True,
            emotional_context=emotional_context,
            document_ids=document_ids,
            client_id=client_id,
            interruption_context=interruption_context,
        )
        retrieval_finished = perf_counter()
        active_documents = document_ids or []
        provenance = (
            "document"
            if chunks
            else "not_in_source"
            if active_documents
            else "general"
        )
        yield {
            "type": "pipeline_stage",
            "response_id": response_id,
            "data": {
                "stage": "retrieval",
                "status": "complete" if active_documents else "skipped",
                "duration_ms": round(
                    (retrieval_finished - retrieval_started) * 1000,
                ),
                "elapsed_ms": round(
                    (retrieval_finished - turn_started) * 1000,
                ),
            },
        }
        yield {
            "type": "turn_context",
            "response_id": response_id,
            "data": {
                **context,
                "provenance": provenance,
                "sources": [
                    {
                        "filename": chunk.get("filename"),
                        "location_type": chunk.get("location_type"),
                        "location_value": chunk.get("location_value"),
                        "score": chunk.get("score"),
                    }
                    for chunk in chunks[:5]
                ],
            },
        }
        tts = StreamingTTS()
        tts.attach(controller)

        response = PausedResponse(
            response_id=response_id,
            session_id=session_id,
            query=query,
            prompt=messages,
            chunks=chunks,
        )
        conversation_state.begin(response)

        if controller.cancelled:
            conversation_state.interrupt()

        ConversationService.add_message(session_id, "user", query)

        try:
            llm_started = perf_counter()
            first_token = True
            for token in self.llm.stream(
                messages,
                max_tokens=settings.VOICE_MAX_TOKENS,
            ):
                if not token:
                    continue

                if first_token:
                    first_token = False
                    now = perf_counter()
                    yield {
                        "type": "pipeline_stage",
                        "response_id": response_id,
                        "data": {
                            "stage": "llm",
                            "status": "first_token",
                            "duration_ms": round(
                                (now - llm_started) * 1000,
                            ),
                            "elapsed_ms": round(
                                (now - turn_started) * 1000,
                            ),
                        },
                    }

                response.append_generated(token)

                # Barge-in cancels presentation, not generation. Draining
                # the Groq stream retains the complete answer for resume.
                if controller.cancelled:
                    tts.reset()
                    continue

                yield {
                    "type": "token",
                    "response_id": response_id,
                    "data": token,
                }

                sentence = tts.append(token)
                if sentence is not None:
                    yield from self._sentence_items(
                        tts=tts,
                        response_id=response_id,
                        sentence=sentence,
                        end_offset=len(response.generated_text),
                        response=response,
                        turn_started=turn_started,
                    )

            if not controller.cancelled:
                sentence = tts.flush_text()
                if sentence is not None:
                    yield from self._sentence_items(
                        tts=tts,
                        response_id=response_id,
                        sentence=sentence,
                        end_offset=len(response.generated_text),
                        response=response,
                        turn_started=turn_started,
                    )

            if controller.cancelled:
                response.mark_interrupted()
            else:
                controller.complete()

            yield {
                "type": "turn_metrics",
                "response_id": response_id,
                "data": {
                    "server_response_ms": round(
                        (perf_counter() - turn_started) * 1000,
                    ),
                    "estimated_output_tokens": round(
                        len(response.generated_text.split()) * 1.3,
                    ),
                    "interrupted": controller.cancelled,
                },
            }

        finally:
            response.mark_generation_complete()

            if (
                not controller.cancelled
                and response.playback_complete
            ):
                conversation_state.finish(response_id)

            tts.detach()

            if controller.cancelled:
                heard = response.acknowledged_text.strip()
                if heard:
                    ConversationService.add_message(
                        session_id,
                        "assistant",
                        heard,
                    )
            elif response.generated_text.strip():
                ConversationService.add_message(
                    session_id,
                    "assistant",
                    response.generated_text,
                )

        if not controller.cancelled:
            memory = MemoryExtractor.extract(query)
            if memory:
                self.memory.store_memory(
                    memory,
                    client_id=client_id or session_id,
                )

    def speak_only(
        self,
        text: str,
        controller,
        session_id: str | None = None,
        log: bool = False,
    ):
        text = text.strip()
        if not text:
            return

        if controller.response_id is None:
            controller.begin()

        response_id = controller.response_id
        tts = StreamingTTS()
        tts.attach(controller)

        try:
            yield {
                "type": "token",
                "response_id": response_id,
                "data": text,
            }

            if not controller.cancelled:
                yield from self._sentence_items(
                    tts=tts,
                    response_id=response_id,
                    sentence=text,
                    end_offset=len(text),
                )

            if not controller.cancelled:
                controller.complete()
        finally:
            tts.detach()

        if (
            not controller.cancelled
            and log
            and session_id
        ):
            ConversationService.add_message(
                session_id,
                "assistant",
                text,
            )

    def stream(
        self,
        query: str,
        session_id: str | None = None,
    ):
        if session_id is None:
            session_id = str(uuid.uuid4())
        return self.stream_response(query, session_id)
