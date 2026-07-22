from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4
import asyncio

from app.services.conversation.conversation_state import ConversationState
from app.services.conversation.response_controller import ResponseController
from app.services.voice.audio_buffer import AudioBuffer
from app.services.voice.state import VoiceState
from app.services.voice.vad import VoiceActivityDetector


@dataclass
class VoiceSession:

    controller: ResponseController = field(
        default_factory=ResponseController
    )

    conversation_state: ConversationState = field(
        default_factory=ConversationState
    )

    voice_task: asyncio.Task | None = None

    pending_interruption_response_id: str | None = None

    interruption_watchdog: asyncio.Task | None = None

    emotion_task: asyncio.Task | None = None

    background_tasks: set[asyncio.Task] = field(
        default_factory=set
    )

    turn_lock: asyncio.Lock = field(
        default_factory=asyncio.Lock
    )

    stt_provider_name: str = "initializing"

    deepgram: Any = None

    whisper_pipeline: Any = None

    fallback_load_task: asyncio.Task | None = None

    pending_consent_audio: bytes | None = None

    playback_controllers: dict[
        str,
        ResponseController,
    ] = field(default_factory=dict)

    pending_playback_segments: dict[
        str,
        set[str],
    ] = field(default_factory=dict)

    playback_events: dict[str, asyncio.Event] = field(
        default_factory=dict
    )

    audio_buffer: AudioBuffer = field(
        default_factory=AudioBuffer
    )

    vad: VoiceActivityDetector = field(
        default_factory=VoiceActivityDetector
    )

    session_id: str = field(
        default_factory=lambda: str(uuid4())
    )

    created_at: datetime = field(
        default_factory=datetime.utcnow
    )

    last_activity: datetime = field(
        default_factory=datetime.utcnow
    )

    state: VoiceState = VoiceState.IDLE

    conversation_id: str | None = None

    voice_id: str | None = None

    model: str | None = None

    metadata: dict = field(default_factory=dict)

    def touch(self):

        self.last_activity = datetime.utcnow()

    def set_state(
        self,
        state: VoiceState,
    ):

        self.state = state

        self.touch()

    def has_active_response(self) -> bool:

        return (
            (
                self.voice_task is not None
                and not self.voice_task.done()
            )
            or bool(self.pending_playback_segments)
        )

    def register_playback_segment(
        self,
        response_id: str,
        segment_id: str,
        controller: ResponseController,
    ) -> None:

        self.playback_controllers[response_id] = controller
        self.pending_playback_segments.setdefault(
            response_id,
            set(),
        ).add(segment_id)
        self.playback_events.setdefault(
            response_id,
            asyncio.Event(),
        )

    def acknowledge_playback_segment(
        self,
        response_id: str,
        segment_id: str,
    ) -> None:

        segments = self.pending_playback_segments.get(
            response_id
        )
        if segments is None:
            return

        segments.discard(segment_id)
        if not segments:
            self.pending_playback_segments.pop(
                response_id,
                None,
            )
            self.playback_controllers.pop(
                response_id,
                None,
            )
            event = self.playback_events.get(response_id)
            if event is not None:
                event.set()

    async def wait_for_playback(
        self,
        response_id: str | None,
        timeout: float = 45.0,
    ) -> bool:

        if not response_id:
            return True

        if response_id not in self.pending_playback_segments:
            return True

        event = self.playback_events.setdefault(
            response_id,
            asyncio.Event(),
        )

        try:
            await asyncio.wait_for(event.wait(), timeout)
            return True
        except asyncio.TimeoutError:
            return False
        finally:
            if event.is_set():
                self.playback_events.pop(response_id, None)

    def _stop_active_presentation(self) -> str | None:
        """Stop TTS/browser playback but leave topic state untouched."""

        if not self.has_active_response():
            return None

        current = self.conversation_state.current
        response_id = (
            current.response_id
            if current is not None
            else self.controller.response_id
        )

        self.controller.cancel()
        for controller in self.playback_controllers.values():
            controller.cancel()

        for event in self.playback_events.values():
            event.set()

        self.playback_controllers.clear()
        self.pending_playback_segments.clear()

        task = self.voice_task
        self.voice_task = None

        if task is not None:
            self.background_tasks.add(task)
            task.add_done_callback(
                self.background_tasks.discard
            )

        return response_id

    def begin_provisional_interruption(self) -> str | None:
        """Stop speech now and wait for STT before pausing the topic."""

        if self.pending_interruption_response_id is not None:
            return self.pending_interruption_response_id

        response_id = self._stop_active_presentation()
        if response_id is not None:
            self.pending_interruption_response_id = response_id
        return response_id

    def clear_pending_interruption(self) -> None:
        self.pending_interruption_response_id = None

        watchdog = self.interruption_watchdog
        self.interruption_watchdog = None
        try:
            current_task = asyncio.current_task()
        except RuntimeError:
            current_task = None
        if (
            watchdog is not None
            and watchdog is not current_task
        ):
            watchdog.cancel()

    def commit_pending_interruption(self):
        """Move a provisionally stopped response to the paused stack."""

        response_id = self.pending_interruption_response_id
        self.clear_pending_interruption()
        if response_id is None:
            return None

        current = self.conversation_state.current
        if current is None or current.response_id != response_id:
            return None

        return self.conversation_state.interrupt()

    def interrupt_active_response(self) -> str | None:
        """Immediately stop and commit an interruption."""

        pending_id = self.pending_interruption_response_id
        if pending_id is not None:
            self.commit_pending_interruption()
            return pending_id

        response_id = self._stop_active_presentation()
        if response_id is not None:
            self.conversation_state.interrupt()
        return response_id

    def set_voice_task(
        self,
        task: asyncio.Task,
        controller: ResponseController,
    ) -> None:

        self.voice_task = task
        self.controller = controller

    async def wait_for_voice_task(self) -> None:
        """
        Wait for the currently running assistant
        response to finish after cancellation.
        """

        if self.voice_task is None:
            return

        task = self.voice_task

        try:
            await task

        except asyncio.CancelledError:
            pass

        finally:
            if self.voice_task is task:
                self.voice_task = None

    async def close(self) -> None:

        self.controller.cancel()
        interruption_watchdog = self.interruption_watchdog
        self.clear_pending_interruption()

        tasks = set(self.background_tasks)
        if interruption_watchdog is not None:
            tasks.add(interruption_watchdog)
        if self.emotion_task is not None:
            tasks.add(self.emotion_task)
        if self.voice_task is not None:
            tasks.add(self.voice_task)
        if self.fallback_load_task is not None:
            tasks.add(self.fallback_load_task)

        for task in tasks:
            task.cancel()

        if self.deepgram is not None:
            await self.deepgram.close()
            self.deepgram = None

        for task in tasks:
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

        self.voice_task = None
        self.background_tasks.clear()
        self.playback_controllers.clear()
        self.pending_playback_segments.clear()
        for event in self.playback_events.values():
            event.set()
        self.playback_events.clear()
        self.conversation_state.clear()
