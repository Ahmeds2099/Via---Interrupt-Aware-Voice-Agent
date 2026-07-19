from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

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