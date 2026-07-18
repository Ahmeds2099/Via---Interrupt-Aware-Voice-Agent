from enum import Enum


class VoiceMessageType(str, Enum):
    CONNECTED = "connected"
    PING = "ping"
    PONG = "pong"
    ERROR = "error"
    CLOSE = "close"

    AUDIO = "audio"

    TRANSCRIPT = "transcript"

    TOKEN = "token"

    TTS = "tts"