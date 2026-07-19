from app.services.conversation_manager import ConversationManager
from app.services.voice.connection_manager import VoiceConnectionManager
from app.services.voice.session import VoiceSession
from app.services.voice.stt_pipeline import VoiceSTTPipeline


class AudioHandler:

    def __init__(self):

        self.pipeline = VoiceSTTPipeline()

        self.manager = ConversationManager()

    async def handle(
        self,
        session: VoiceSession,
        connection_manager: VoiceConnectionManager,
        data: bytes,
    ) -> None:

        session.touch()

        segment = session.vad.update(data)

        if segment is None:
            return

        print(
            "[VOICE] Speech segment complete "
            f"({len(segment.audio)} bytes)"
        )

        transcript = await self.pipeline.process(
            session=session,
            audio=segment.audio,
        )

        if not transcript:

            print("[VOICE] Empty transcript")

            return

        print(f"[TRANSCRIPT] {transcript}")

        await connection_manager.send_json(
            session.session_id,
            {
                "type": "transcript",
                "text": transcript,
            },
        )

        #
        # Conversation Layer
        #

        await connection_manager.send_json(

    session.session_id,

    {

        "type": "assistant_stream_start",

    },

)

        await connection_manager.send_json(

    session.session_id,

    {

        "type": "assistant_audio_start",

    },

)

        for item in self.manager.stream_voice(

            query=transcript,

            session_id=session.session_id,

        ):

            if item["type"] == "token":

                await connection_manager.send_json(

                    session.session_id,

                {

                    "type": "assistant_stream",

                    "token": item["data"],

                },

            )

            else:

                await connection_manager.send_bytes(

                    session.session_id,

                    item["data"],

                )

            await connection_manager.send_json(

                session.session_id,

                {

                    "type": "assistant_stream_end",

                },

            )

            await connection_manager.send_json(

                session.session_id,

                {

                    "type": "assistant_audio_end",

                },

            )

        