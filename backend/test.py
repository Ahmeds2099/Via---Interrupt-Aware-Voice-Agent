from app.services.voice.session_manager import VoiceSessionManager
from app.services.voice.streaming_stt import StreamingSTT

manager = VoiceSessionManager()
session = manager.create_session()

stt = StreamingSTT()

fake_audio = b"\x00" * 32000

result = stt.append_audio(session, fake_audio)

print(result)