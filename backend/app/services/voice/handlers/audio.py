from __future__ import annotations

import asyncio
import re

from app.core.config import settings
from app.services.conversation.response_controller import ResponseController
from app.services.conversation_service import ConversationService
from app.services.emotion import EmotionResult, emotion_provider
from app.services.session_repository import session_repository
from app.services.conversation_manager import ConversationManager
from app.services.voice.async_bridge import iter_in_thread
from app.services.voice.connection_manager import VoiceConnectionManager
from app.services.voice.deepgram import (
    DeepgramStreamingSTT,
    TranscriptEvent,
    normalize_transcript,
)
from app.services.voice.resume_intent import (
    classify_interruption,
    classify_resume_intent,
    is_resume_context_request,
)
from app.services.voice.session import VoiceSession
from app.services.voice.stt_pipeline import VoiceSTTPipeline
from app.services.voice.vad import SpeechSegment, SpeechStart


DECLINE_ACK_TEXT = (
    "Okay."
)

RESUME_PREFIX = "Returning to that thought - "

FALSE_INTERRUPTION_RESUME_PREFIX = (
    "I didn't catch that, so I'll continue. "
)

FALLBACK_WARNING_TEXT = (
    "I'm having trouble with my primary transcription service. "
    "I can continue using a lower-accuracy local transcription "
    "model, or you can stop and check the connection. Would you "
    "like me to continue?"
)

FALLBACK_ACCEPTED_TEXT = (
    "Okay. I'll continue with the local transcription model. "
    "Please repeat what you were saying."
)

FALLBACK_DECLINED_TEXT = (
    "Okay. Voice transcription is paused so you can check the "
    "connection or configuration."
)

FALLBACK_CLARIFY_TEXT = (
    "Please say yes or no, or use one of the choices on screen."
)


def _resume_excerpt(
    text: str,
    max_words: int = 70,
) -> tuple[str, int, bool]:
    """Return a short, sentence-aware prefix for spoken resume."""

    stripped = text.lstrip()
    leading = len(text) - len(stripped)
    if not stripped:
        return "", len(text), False

    sentence_ends = [
        match.end()
        for match in re.finditer(
            r".*?[.!?](?:\s+|$)",
            stripped,
        )
        if match.group(0).strip()
    ]

    chosen_end = 0
    for end in sentence_ends:
        candidate = stripped[:end].strip()
        if len(candidate.split()) > max_words:
            if chosen_end:
                break
            words = list(re.finditer(r"\S+", stripped[:end]))
            chosen_end = words[max_words - 1].end()
            break
        chosen_end = end
        if len(candidate.split()) >= max_words:
            break

    if not chosen_end:
        words = list(re.finditer(r"\S+", stripped))
        if len(words) <= max_words:
            chosen_end = len(stripped)
        else:
            chosen_end = words[max_words - 1].end()

    excerpt = stripped[:chosen_end].strip()
    consumed = leading + chosen_end
    has_more = bool(text[consumed:].strip())
    return excerpt, consumed, has_more


def _paused_topic_reminder(query: str) -> str:
    """Build a short reminder without starting another LLM turn."""

    words = re.sub(r"\s+", " ", query).strip(" .?!").split()
    if len(words) > 18:
        topic = " ".join(words[:18]) + "..."
    else:
        topic = " ".join(words)

    return f"We were discussing: {topic}."


class AudioHandler:
    def __init__(self):
        self.manager = ConversationManager()
        self.emotion_provider = emotion_provider

    async def start_session(
        self,
        session: VoiceSession,
        connection_manager: VoiceConnectionManager,
    ) -> None:
        # Emotion2Vec stays cold until the first completed utterance. Merely
        # opening the voice socket must not allocate the local model.
        await connection_manager.send_json(
            session.session_id,
            {
                "type": "emotion_status",
                **self.emotion_provider.status,
            },
        )

        provider = settings.VOICE_STT_PROVIDER

        if provider == "whisper":
            try:
                await self._load_whisper(session)
            except Exception as exc:
                session.stt_provider_name = "disabled"
                await self._send_error(
                    session,
                    connection_manager,
                    code="whisper_unavailable",
                    message=str(exc),
                    recoverable=False,
                )
                return

            session.stt_provider_name = "whisper"
            await connection_manager.send_json(
                session.session_id,
                {
                    "type": "stt_ready",
                    "provider": "whisper",
                    "quality": "fallback",
                },
            )
            return

        if provider != "deepgram":
            session.stt_provider_name = "disabled"
            await self._send_error(
                session,
                connection_manager,
                code="invalid_stt_provider",
                message=(
                    "VOICE_STT_PROVIDER must be deepgram or whisper"
                ),
                recoverable=False,
            )
            return

        async def on_transcript(event: TranscriptEvent) -> None:
            await self._handle_transcript_event(
                session,
                connection_manager,
                event,
            )

        async def on_error(reason: str) -> None:
            await self._begin_fallback(
                session,
                connection_manager,
                reason,
            )

        deepgram = DeepgramStreamingSTT(
            on_transcript=on_transcript,
            on_error=on_error,
        )
        session.deepgram = deepgram

        try:
            await deepgram.start()
        except Exception as exc:
            await self._begin_fallback(
                session,
                connection_manager,
                str(exc),
            )
            return

        session.stt_provider_name = "deepgram"
        await connection_manager.send_json(
            session.session_id,
            {
                "type": "stt_ready",
                "provider": "deepgram",
                "model": settings.DEEPGRAM_MODEL,
                "language": settings.DEEPGRAM_LANGUAGE,
            },
        )

    async def _load_whisper(
        self,
        session: VoiceSession,
    ) -> VoiceSTTPipeline:
        if session.whisper_pipeline is not None:
            return session.whisper_pipeline

        if session.fallback_load_task is None:
            session.fallback_load_task = asyncio.create_task(
                asyncio.to_thread(VoiceSTTPipeline),
                name="load-whisper-fallback",
            )

        pipeline = await asyncio.shield(
            session.fallback_load_task
        )
        session.whisper_pipeline = pipeline
        return pipeline

    async def _begin_fallback(
        self,
        session: VoiceSession,
        connection_manager: VoiceConnectionManager,
        reason: str,
    ) -> None:
        if session.metadata.get("awaiting_fallback_consent"):
            return
        if session.stt_provider_name in {"whisper", "disabled"}:
            return

        if not settings.VOICE_ALLOW_WHISPER_FALLBACK:
            session.stt_provider_name = "disabled"
            await self._send_error(
                session,
                connection_manager,
                code="deepgram_unavailable",
                message=reason,
                recoverable=False,
            )
            return

        was_mid_session = session.stt_provider_name == "deepgram"
        session.metadata["awaiting_fallback_consent"] = True
        session.metadata["fallback_was_mid_session"] = was_mid_session
        session.metadata["deepgram_failure_reason"] = reason
        session.stt_provider_name = "fallback_pending"

        if session.deepgram is not None:
            await session.deepgram.close()
            session.deepgram = None

        interrupted_id = session.interrupt_active_response()
        if interrupted_id is not None:
            await connection_manager.send_json(
                session.session_id,
                {
                    "type": "interrupted",
                    "response_id": interrupted_id,
                },
            )

        await self._send_error(
            session,
            connection_manager,
            code="deepgram_unavailable",
            message=reason,
            recoverable=True,
        )
        await connection_manager.send_json(
            session.session_id,
            {
                "type": "stt_fallback_required",
                "from_provider": "deepgram",
                "fallback_provider": "whisper",
                "message": FALLBACK_WARNING_TEXT,
            },
        )

        if session.fallback_load_task is None:
            session.fallback_load_task = asyncio.create_task(
                asyncio.to_thread(VoiceSTTPipeline),
                name="load-whisper-fallback",
            )

        self._schedule_system_message(
            session,
            connection_manager,
            FALLBACK_WARNING_TEXT,
        )

        try:
            await self._load_whisper(session)
        except Exception as exc:
            session.stt_provider_name = "disabled"
            session.metadata["awaiting_fallback_consent"] = False
            await self._send_error(
                session,
                connection_manager,
                code="whisper_unavailable",
                message=str(exc),
                recoverable=False,
            )
            return

        if session.pending_consent_audio:
            audio = session.pending_consent_audio
            session.pending_consent_audio = None
            asyncio.create_task(
                self._process_whisper_segment(
                    session,
                    connection_manager,
                    audio,
                )
            )

    async def _send_error(
        self,
        session: VoiceSession,
        connection_manager: VoiceConnectionManager,
        code: str,
        message: str,
        recoverable: bool,
    ) -> None:
        await connection_manager.send_json(
            session.session_id,
            {
                "type": "error",
                "code": code,
                "message": message,
                "recoverable": recoverable,
            },
        )

    async def _stream_items(
        self,
        session: VoiceSession,
        connection_manager: VoiceConnectionManager,
        controller: ResponseController,
        items,
    ) -> None:
        async for item in iter_in_thread(items):
            if controller.cancelled:
                continue

            item_type = item["type"]

            if item_type == "token":
                await connection_manager.send_json(
                    session.session_id,
                    {
                        "type": "assistant_stream",
                        "response_id": item["response_id"],
                        "token": item["data"],
                    },
                )
            elif item_type == "audio":
                await connection_manager.send_bytes(
                    session.session_id,
                    item["data"],
                )
            elif item_type == "segment_start":
                session.register_playback_segment(
                    item["data"]["response_id"],
                    item["data"]["segment_id"],
                    controller,
                )
                await connection_manager.send_json(
                    session.session_id,
                    {
                        "type": "assistant_segment_start",
                        **item["data"],
                    },
                )
            elif item_type == "segment_end":
                await connection_manager.send_json(
                    session.session_id,
                    {
                        "type": "assistant_segment_end",
                        **item["data"],
                    },
                )
            elif item_type in {
                "pipeline_stage",
                "turn_context",
                "turn_metrics",
            }:
                await connection_manager.send_json(
                    session.session_id,
                    {
                        "type": item_type,
                        "response_id": item.get("response_id"),
                        **item["data"],
                    },
                )

    async def _emit_stream(
        self,
        session: VoiceSession,
        connection_manager: VoiceConnectionManager,
        controller: ResponseController,
        items,
    ) -> None:
        response_id = controller.response_id
        await connection_manager.send_json(
            session.session_id,
            {
                "type": "assistant_stream_start",
                "response_id": response_id,
            },
        )
        await connection_manager.send_json(
            session.session_id,
            {
                "type": "voice_state",
                "state": "thinking",
                "response_id": response_id,
            },
        )
        await connection_manager.send_json(
            session.session_id,
            {
                "type": "assistant_audio_start",
                "response_id": response_id,
            },
        )

        try:
            await self._stream_items(
                session,
                connection_manager,
                controller,
                items,
            )
        finally:
            await connection_manager.send_json(
                session.session_id,
                {
                    "type": "assistant_stream_end",
                    "response_id": response_id,
                },
            )
            await connection_manager.send_json(
                session.session_id,
                {
                    "type": "assistant_audio_end",
                    "response_id": response_id,
                },
            )
            await connection_manager.send_json(
                session.session_id,
                {
                    "type": "voice_state",
                    "state": "idle",
                    "response_id": response_id,
                },
            )

    def _new_controller(self) -> ResponseController:
        controller = ResponseController()
        controller.begin()
        return controller

    def _schedule_response(
        self,
        session: VoiceSession,
        connection_manager: VoiceConnectionManager,
        transcript: str,
        resume_policy: str = "none",
        interruption_context: dict | None = None,
    ) -> None:
        controller = self._new_controller()

        async def runner() -> None:
            current_task = asyncio.current_task()
            try:
                await self._emit_stream(
                    session,
                    connection_manager,
                    controller,
                    self.manager.stream_voice(
                        query=transcript,
                        session_id=session.session_id,
                        controller=controller,
                        conversation_state=(
                            session.conversation_state
                        ),
                        emotional_context=session.metadata.get(
                            "emotion_state"
                        ),
                        document_ids=session.metadata.get(
                            "active_document_ids"
                        ),
                        client_id=session.metadata.get(
                            "client_id",
                            session.session_id,
                        ),
                        interruption_context=interruption_context,
                    ),
                )

                await session.wait_for_playback(
                    controller.response_id
                )

                if not controller.cancelled and resume_policy == "confirm" and session.conversation_state.has_paused():
                    session.metadata["awaiting_resume"] = True
                elif not controller.cancelled and resume_policy == "automatic" and session.conversation_state.has_paused():
                    self._schedule_resume(session, connection_manager)
                elif not controller.cancelled and not session.conversation_state.has_paused():
                    session.metadata["awaiting_resume"] = False
            except Exception as exc:
                await self._send_error(
                    session,
                    connection_manager,
                    code="response_failed",
                    message=str(exc),
                    recoverable=True,
                )
            finally:
                if session.voice_task is current_task:
                    session.voice_task = None

        task = asyncio.create_task(
            runner(),
            name="voice-response",
        )
        session.set_voice_task(task, controller)

    def _schedule_system_message(
        self,
        session: VoiceSession,
        connection_manager: VoiceConnectionManager,
        text: str,
    ) -> None:
        controller = self._new_controller()

        async def runner() -> None:
            current_task = asyncio.current_task()
            try:
                await self._emit_stream(
                    session,
                    connection_manager,
                    controller,
                    self.manager.speak_only(
                        text,
                        controller=controller,
                    ),
                )
            except Exception as exc:
                await self._send_error(
                    session,
                    connection_manager,
                    code="tts_failed",
                    message=str(exc),
                    recoverable=True,
                )
            finally:
                if session.voice_task is current_task:
                    session.voice_task = None

        task = asyncio.create_task(
            runner(),
            name="voice-system-message",
        )
        session.set_voice_task(task, controller)

    def _schedule_resume(
        self,
        session: VoiceSession,
        connection_manager: VoiceConnectionManager,
        prefix: str = RESUME_PREFIX,
    ) -> None:
        controller = self._new_controller()

        async def runner() -> None:
            current_task = asyncio.current_task()
            session.metadata["awaiting_resume"] = False
            paused = session.conversation_state.resume()

            try:
                consumed = 0

                if paused is None:
                    text = "There isn't a paused response to continue."
                else:
                    await asyncio.to_thread(
                        paused.wait_for_generation,
                        10.0,
                    )
                    remaining = paused.remaining_text.strip()
                    if remaining:
                        # Voice responses are already capped. Resume the full
                        # remainder instead of creating another confirmation
                        # loop after an arbitrary excerpt.
                        consumed = len(paused.remaining_text)
                        text = prefix + remaining
                    else:
                        text = (
                            "I had already finished that thought. "
                            "What would you like to discuss next?"
                        )

                await self._emit_stream(
                    session,
                    connection_manager,
                    controller,
                    self.manager.speak_only(
                        text,
                        controller=controller,
                        session_id=session.session_id,
                        log=paused is not None,
                    ),
                )

                playback_finished = await session.wait_for_playback(
                    controller.response_id
                )

                if (
                    paused is not None
                    and not controller.cancelled
                    and playback_finished
                ):
                    paused.consume_remaining(consumed)

                    session.conversation_state.finish(paused.response_id)
            except Exception as exc:
                await self._send_error(
                    session,
                    connection_manager,
                    code="resume_failed",
                    message=str(exc),
                    recoverable=True,
                )
            finally:
                if session.voice_task is current_task:
                    session.voice_task = None

        task = asyncio.create_task(runner(), name="voice-resume")
        session.set_voice_task(task, controller)

    def _arm_interruption_watchdog(
        self,
        session: VoiceSession,
        connection_manager: VoiceConnectionManager,
    ) -> None:
        """Recover when VAD stops Via but STT confirms no utterance."""

        previous = session.interruption_watchdog
        if previous is not None:
            previous.cancel()

        async def watchdog() -> None:
            try:
                await asyncio.sleep(
                    settings
                    .VOICE_INTERRUPTION_CONFIRM_TIMEOUT_SECONDS
                )
                async with session.turn_lock:
                    if (
                        session.pending_interruption_response_id
                        is None
                    ):
                        return

                    interrupted = (
                        session.commit_pending_interruption()
                    )
                    await connection_manager.send_json(
                        session.session_id,
                        {"type": "interruption_recovered"},
                    )

                    if interrupted is not None:
                        self._schedule_resume(
                            session,
                            connection_manager,
                            prefix=(
                                FALSE_INTERRUPTION_RESUME_PREFIX
                            ),
                        )
            except asyncio.CancelledError:
                return
            finally:
                if session.interruption_watchdog is current_task:
                    session.interruption_watchdog = None

        current_task = asyncio.create_task(
            watchdog(),
            name="interruption-confirmation-watchdog",
        )
        session.interruption_watchdog = current_task

    def _schedule_decline(
        self,
        session: VoiceSession,
        connection_manager: VoiceConnectionManager,
    ) -> None:
        session.metadata["awaiting_resume"] = False
        session.conversation_state.discard_paused()
        self._schedule_system_message(
            session,
            connection_manager,
            DECLINE_ACK_TEXT,
        )

    async def _handle_transcript_event(
        self,
        session: VoiceSession,
        connection_manager: VoiceConnectionManager,
        event: TranscriptEvent,
    ) -> None:
        if not event.is_final:
            if (
                event.text.strip()
                and session.pending_interruption_response_id
                is not None
            ):
                self._arm_interruption_watchdog(
                    session,
                    connection_manager,
                )
            await connection_manager.send_json(
                session.session_id,
                {
                    "type": "transcript_interim",
                    "text": event.text,
                    "provider": event.provider,
                },
            )
            return

        transcript = event.text.strip()
        if not transcript:
            return

        async with session.turn_lock:
            session.commit_pending_interruption()

            await self._consume_emotion_result(
                session,
                connection_manager,
                transcript,
                event.confidence,
            )

            await connection_manager.send_json(
                session.session_id,
                {
                    "type": "transcript",
                    "text": transcript,
                    "provider": event.provider,
                },
            )

            if session.metadata.get("awaiting_fallback_consent"):
                intent = classify_resume_intent(transcript)
                if intent == "yes":
                    await self._accept_fallback(
                        session,
                        connection_manager,
                    )
                elif intent == "no":
                    await self._decline_fallback(
                        session,
                        connection_manager,
                    )
                else:
                    self._schedule_system_message(
                        session,
                        connection_manager,
                        FALLBACK_CLARIFY_TEXT,
                    )
                return

            if session.conversation_state.has_paused():
                if is_resume_context_request(transcript):
                    paused = session.conversation_state.peek_paused()
                    if paused is not None:
                        self._schedule_system_message(
                            session,
                            connection_manager,
                            _paused_topic_reminder(paused.query),
                        )
                    return

                paused = session.conversation_state.peek_paused()
                classifier = (
                    self.manager.llm.classify_interruption
                    if settings.GROQ_API_KEY
                    else None
                )
                decision = await asyncio.to_thread(
                    classify_interruption,
                    transcript,
                    awaiting_resume=bool(
                        session.metadata.get("awaiting_resume")
                    ),
                    classifier=classifier,
                )

                if decision.intent in {"resume", "backchannel"}:
                    self._schedule_resume(
                        session,
                        connection_manager,
                    )
                    return
                if decision.intent in {"stop", "decline"}:
                    self._schedule_decline(
                        session,
                        connection_manager,
                    )
                    return

                if decision.resume_policy == "discard":
                    session.metadata["awaiting_resume"] = False
                    session.conversation_state.discard_paused()

                context = {
                    "mode": decision.intent,
                    "paused_topic": paused.query if paused else "",
                }
                self._schedule_response(
                    session,
                    connection_manager,
                    transcript,
                    resume_policy=decision.resume_policy,
                    interruption_context=context,
                )
                return

            # A stop utterance while Via is otherwise idle is still a control
            # command, not a new question for the LLM.
            idle_decision = classify_interruption(transcript)
            if idle_decision.intent == "stop":
                self._schedule_system_message(
                    session,
                    connection_manager,
                    "Okay.",
                )
                return

            if session.has_active_response():
                response_id = session.interrupt_active_response()
                if response_id is not None:
                    await connection_manager.send_json(
                        session.session_id,
                        {
                            "type": "interrupted",
                            "response_id": response_id,
                        },
                    )

            self._schedule_response(
                session,
                connection_manager,
                transcript,
            )

    def _begin_emotion_analysis(
        self,
        session: VoiceSession,
        audio: bytes,
        connection_manager: VoiceConnectionManager,
    ) -> None:
        if not settings.VOICE_ENABLE_EMOTION or not audio:
            return

        previous = session.emotion_task
        if previous is not None and not previous.done():
            previous.cancel()

        session.emotion_task = asyncio.create_task(
            asyncio.to_thread(
                self.emotion_provider.analyze,
                audio,
            ),
            name="emotion-analysis",
        )

    async def _publish_emotion_result(
        self,
        session: VoiceSession,
        connection_manager: VoiceConnectionManager,
        result: EmotionResult,
    ) -> None:
        result, history = self.emotion_provider.smooth(
            result,
            session.metadata.get("emotion_history", []),
        )
        session.metadata["emotion_history"] = history
        payload = result.to_dict()
        session.metadata["emotion_state"] = payload
        await connection_manager.send_json(
            session.session_id,
            {"type": "emotion_update", **payload},
        )
        persistence_task = asyncio.create_task(
            asyncio.to_thread(
                ConversationService.update_state,
                session.session_id,
                emotion_state=payload,
                doubt_counter=(
                    int(
                        ConversationService.get_state(
                            session.session_id
                        ).get("doubt_counter", 0)
                    )
                    + (1 if result.clarification_mode else 0)
                ),
            ),
            name="persist-emotion-state",
        )
        session.background_tasks.add(persistence_task)
        persistence_task.add_done_callback(
            session.background_tasks.discard
        )

    async def _consume_emotion_result(
        self,
        session: VoiceSession,
        connection_manager: VoiceConnectionManager,
        transcript: str,
        confidence: float | None,
    ) -> None:
        task = session.emotion_task
        if task is None:
            current = session.metadata.get("emotion_state")
            if current:
                derived = self.emotion_provider.derive_doubt(
                    transcript,
                    confidence,
                    current.get("label", "unknown"),
                    float(current.get("confidence", 0)),
                )
                # Stale doubt decays instead of remaining at its historical
                # maximum forever.
                current["doubt_score"] = max(
                    derived,
                    float(current.get("doubt_score", 0)) * 0.45,
                )
                current["clarification_mode"] = (
                    current["doubt_score"]
                    >= settings.EMOTION_DOUBT_THRESHOLD
                )
            return

        session.emotion_task = None
        try:
            result = await asyncio.wait_for(
                asyncio.shield(task),
                settings.EMOTION_WAIT_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            async def publish_later() -> None:
                try:
                    late_result = await task
                    late_result = self.emotion_provider.enrich(
                        late_result,
                        transcript,
                        confidence,
                    )
                    if (
                        self.emotion_provider.UNDERSTANDING.search(transcript)
                        and not self.emotion_provider.UNCERTAINTY.search(transcript)
                    ):
                        session.metadata["emotion_history"] = []
                    await self._publish_emotion_result(
                        session,
                        connection_manager,
                        late_result,
                    )
                except (asyncio.CancelledError, Exception):
                    return

            late_task = asyncio.create_task(
                publish_later(),
                name="publish-late-emotion",
            )
            session.background_tasks.add(late_task)
            late_task.add_done_callback(
                session.background_tasks.discard
            )
            return
        except (asyncio.CancelledError, Exception):
            return

        result = self.emotion_provider.enrich(
            result,
            transcript,
            confidence,
        )
        if (
            self.emotion_provider.UNDERSTANDING.search(transcript)
            and not self.emotion_provider.UNCERTAINTY.search(transcript)
        ):
            session.metadata["emotion_history"] = []
        await self._publish_emotion_result(
            session,
            connection_manager,
            result,
        )

    async def _process_whisper_segment(
        self,
        session: VoiceSession,
        connection_manager: VoiceConnectionManager,
        audio: bytes,
    ) -> None:
        try:
            pipeline = await self._load_whisper(session)
            transcript = await pipeline.process(
                session=session,
                audio=audio,
            )
        except Exception as exc:
            await self._send_error(
                session,
                connection_manager,
                code="whisper_transcription_failed",
                message=str(exc),
                recoverable=False,
            )
            return

        if transcript:
            transcript = normalize_transcript(transcript)
            await self._handle_transcript_event(
                session,
                connection_manager,
                TranscriptEvent(
                    text=transcript,
                    is_final=True,
                    speech_final=True,
                    provider="whisper",
                ),
            )

    async def _accept_fallback(
        self,
        session: VoiceSession,
        connection_manager: VoiceConnectionManager,
    ) -> None:
        if not session.metadata.get("awaiting_fallback_consent"):
            return

        try:
            await self._load_whisper(session)
        except Exception as exc:
            session.stt_provider_name = "disabled"
            await self._send_error(
                session,
                connection_manager,
                code="whisper_unavailable",
                message=str(exc),
                recoverable=False,
            )
            return

        session.metadata["awaiting_fallback_consent"] = False
        session.stt_provider_name = "whisper"
        session.pending_consent_audio = None

        await connection_manager.send_json(
            session.session_id,
            {
                "type": "stt_provider_changed",
                "provider": "whisper",
                "quality": "fallback",
            },
        )
        self._schedule_system_message(
            session,
            connection_manager,
            FALLBACK_ACCEPTED_TEXT,
        )

    async def _decline_fallback(
        self,
        session: VoiceSession,
        connection_manager: VoiceConnectionManager,
    ) -> None:
        if not session.metadata.get("awaiting_fallback_consent"):
            return

        session.metadata["awaiting_fallback_consent"] = False
        session.stt_provider_name = "disabled"
        session.pending_consent_audio = None

        await connection_manager.send_json(
            session.session_id,
            {
                "type": "stt_provider_changed",
                "provider": "disabled",
            },
        )
        self._schedule_system_message(
            session,
            connection_manager,
            FALLBACK_DECLINED_TEXT,
        )

    async def handle_control(
        self,
        session: VoiceSession,
        connection_manager: VoiceConnectionManager,
        message: dict,
    ) -> None:
        message_type = message.get("type")

        if message_type == "playback_ack":
            response_id = message.get("response_id")
            segment_id = message.get("segment_id")
            if response_id and segment_id:
                session.acknowledge_playback_segment(
                    response_id,
                    segment_id,
                )
                session.conversation_state.acknowledge_segment(
                    response_id,
                    segment_id,
                )
            return

        if message_type == "playback_started":
            await connection_manager.send_json(
                session.session_id,
                {
                    "type": "pipeline_stage",
                    "response_id": message.get("response_id"),
                    "stage": "playback",
                    "status": "started",
                    "segment_id": message.get("segment_id"),
                    "client_elapsed_ms": message.get("client_elapsed_ms"),
                },
            )
            await connection_manager.send_json(
                session.session_id,
                {
                    "type": "voice_state",
                    "state": "speaking",
                    "response_id": message.get("response_id"),
                },
            )
            return

        if message_type == "session_init":
            client_id = str(message.get("client_id") or "").strip()
            if not client_id or len(client_id) > 128:
                await self._send_error(
                    session,
                    connection_manager,
                    code="invalid_client_id",
                    message="A valid client ID is required.",
                    recoverable=True,
                )
                return

            state = await asyncio.to_thread(
                ConversationService.bind,
                session.session_id,
                client_id,
            )
            has_requested_documents = "document_ids" in message
            requested_documents = message.get("document_ids") or []
            active_documents = [
                str(document_id)
                for document_id in (
                    requested_documents
                    if has_requested_documents
                    else state.get("active_documents", [])
                )
                if document_id
            ][:20]
            session.metadata["client_id"] = client_id
            session.metadata["active_document_ids"] = active_documents
            session.metadata["emotion_state"] = state.get(
                "emotion_state",
                {},
            )
            if has_requested_documents:
                await asyncio.to_thread(
                    ConversationService.update_state,
                    session.session_id,
                    active_documents=active_documents,
                )
            await connection_manager.send_json(
                session.session_id,
                {
                    "type": "session_restored",
                    "message_count": len(state.get("messages", [])),
                    "memory_count": len(state.get("memories", [])),
                    "document_ids": active_documents,
                    "persistence": session_repository.status,
                },
            )
            return

        if message_type == "set_document_context":
            document_ids = [
                str(document_id)
                for document_id in (message.get("document_ids") or [])
                if document_id
            ][:20]
            session.metadata["active_document_ids"] = document_ids
            await asyncio.to_thread(
                ConversationService.update_state,
                session.session_id,
                active_documents=document_ids,
            )
            await connection_manager.send_json(
                session.session_id,
                {
                    "type": "document_context_updated",
                    "document_ids": document_ids,
                },
            )
            return

        if message_type == "stt_fallback_choice":
            choice = message.get("choice")
            if choice == "continue":
                await self._accept_fallback(
                    session,
                    connection_manager,
                )
            elif choice == "stop":
                await self._decline_fallback(
                    session,
                    connection_manager,
                )

    async def handle(
        self,
        session: VoiceSession,
        connection_manager: VoiceConnectionManager,
        data: bytes,
    ) -> None:
        session.touch()

        if session.stt_provider_name == "deepgram":
            if session.deepgram is not None:
                await session.deepgram.send_audio(data)

        event = session.vad.update(data)

        if isinstance(event, SpeechStart):
            if session.stt_provider_name == "deepgram":
                response_id = (
                    session.begin_provisional_interruption()
                )
            else:
                response_id = session.interrupt_active_response()
            if response_id is not None:
                await connection_manager.send_json(
                    session.session_id,
                    {
                        "type": "interrupted",
                        "response_id": response_id,
                    },
                )
                if session.stt_provider_name == "deepgram":
                    self._arm_interruption_watchdog(
                        session,
                        connection_manager,
                    )
            return

        if not isinstance(event, SpeechSegment):
            return

        self._begin_emotion_analysis(
            session,
            event.audio,
            connection_manager,
        )

        if session.stt_provider_name in {
            "whisper",
            "fallback_pending",
        }:
            if session.whisper_pipeline is None:
                session.pending_consent_audio = event.audio
                return

            asyncio.create_task(
                self._process_whisper_segment(
                    session,
                    connection_manager,
                    event.audio,
                )
            )
