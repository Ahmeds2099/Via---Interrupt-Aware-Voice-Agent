import uuid

from app.core.prompts import SYSTEM_PROMPT
from app.services.conversation_service import ConversationService
from app.services.embedder import EmbeddingService
from app.services.llm import LLMService
from app.services.prompt_builder import PromptBuilder
from app.services.qdrant_service import QdrantService
from app.services.memory_extractor import MemoryExtractor
from app.services.memory_service import MemoryService
from app.services.tts.stream import StreamingTTS


class ConversationManager:

    def __init__(self):
        self.embedder = EmbeddingService()
        self.llm = LLMService()
        self.memory = MemoryService()
        self.tts = StreamingTTS()

    def build_messages(
        self,
        query: str,
        session_id: str,
    ) -> tuple[list[dict], list[dict]]:

        query_vector = self.embedder.embed_query(query)

        chunks = QdrantService.search(query_vector)

        prompt = PromptBuilder.build(query, chunks)

        history = ConversationService.get_messages(session_id)

        memories = self.memory.search(query)

        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            }
        ]

        if memories:

            memory_block = "\n".join(
                f"- {m}"
                for m in memories
            )

            messages.append(
                {
                    "role": "system",
                    "content":
                        "Known user information:\n"
                        + memory_block,
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

        return messages, chunks

    def generate_response(
        self,
        query: str,
        session_id: str,
    ) -> dict:

        messages, chunks = self.build_messages(
            query,
            session_id,
        )

        answer = self.llm.generate(messages)

        memory = MemoryExtractor.extract(query)

        if memory:
            self.memory.store_memory(memory)

        ConversationService.add_message(
            session_id,
            "user",
            query,
        )

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
    ) -> dict:

        if session_id is None:
            session_id = str(uuid.uuid4())

        return self.generate_response(
            query,
            session_id,
        )

    def stream_response(
        self,
        query: str,
        session_id: str,
    ):

        messages, _ = self.build_messages(
            query,
            session_id,
        )

        accumulated = ""

        for token in self.llm.stream(messages):

            accumulated += token

            yield token

        ConversationService.add_message(
            session_id,
            "user",
            query,
        )

        ConversationService.add_message(
            session_id,
            "assistant",
            accumulated,
        )

    def stream_voice(
        self,
        query: str,
        session_id: str,
    ):

        print("=" * 60)
        print("[VOICE] stream_voice() started")
        print(f"[VOICE] Query: {query}")
        print("=" * 60)

        messages, _ = self.build_messages(
            query,
            session_id,
        )

        accumulated = ""

        tts = self.tts

        try:

            for token in self.llm.stream(messages):

                print(f"[LLM] Token -> {repr(token)}")

                accumulated += token

                yield {
                    "type": "token",
                    "data": token,
                }

                try:

                    chunk_count = 0

                    print("[TTS] feed()")

                    for audio in tts.feed(token):

                        chunk_count += 1

                        print(
                            f"[TTS] Audio Chunk "
                            f"{chunk_count} "
                            f"({len(audio)} bytes)"
                        )

                        yield {
                            "type": "audio",
                            "data": audio,
                        }

                    if chunk_count == 0:

                        print(
                            "[TTS] feed() produced no audio "
                            "(sentence not complete yet)"
                        )

                except Exception as e:

                    print(
                        "[TTS ERROR during feed()]",
                        repr(e),
                    )

            print("[VOICE] LLM finished")

            try:

                print("[TTS] flush()")

                flush_chunks = 0

                for audio in tts.flush():

                    flush_chunks += 1

                    print(
                        f"[TTS] Flush Chunk "
                        f"{flush_chunks} "
                        f"({len(audio)} bytes)"
                    )

                    yield {
                        "type": "audio",
                        "data": audio,
                    }

                if flush_chunks == 0:

                    print(
                        "[TTS] flush() produced no audio"
                    )

            except Exception as e:

                print(
                    "[TTS ERROR during flush()]",
                    repr(e),
                )

        except Exception as e:

            print(
                "[VOICE ERROR]",
                repr(e),
            )

            raise

        finally:

            ConversationService.add_message(
                session_id,
                "user",
                query,
            )

            ConversationService.add_message(
                session_id,
                "assistant",
                accumulated,
            )

            print("[VOICE] Conversation saved")
            print("=" * 60)

    def stream(
        self,
        query: str,
        session_id: str | None = None,
    ):

        if session_id is None:
            session_id = str(uuid.uuid4())

        return self.stream_response(
            query,
            session_id,
        )