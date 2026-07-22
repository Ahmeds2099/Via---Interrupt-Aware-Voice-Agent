import unittest
import asyncio

from app.services.conversation.conversation_state import ConversationState
from app.services.conversation.paused_response import PausedResponse
from app.services.conversation.response_controller import ResponseController
from app.core.config import settings
from app.services.voice.deepgram import (
    DeepgramStreamingSTT,
    normalize_transcript,
)
from app.services.voice.handlers.audio import (
    AudioHandler,
    _paused_topic_reminder,
    _resume_excerpt,
)
from app.services.voice.resume_intent import (
    classify_interruption,
    classify_resume_intent,
    is_resume_context_request,
)
from app.services.voice.session import VoiceSession


class FakeConnectionManager:
    def __init__(self):
        self.messages = []

    async def send_json(self, _session_id, payload):
        self.messages.append(payload)


class ResumeIntentTests(unittest.TestCase):
    def test_audio_handler_module_imports(self):
        self.assertTrue(callable(AudioHandler))

    def test_short_confirmations(self):
        self.assertEqual(classify_resume_intent("yes"), "yes")
        self.assertEqual(
            classify_resume_intent("yeah go ahead"),
            "yes",
        )
        self.assertEqual(classify_resume_intent("no thanks"), "no")

    def test_via_name_normalization(self):
        self.assertEqual(
            normalize_transcript("hello vee ah"),
            "hello Via",
        )
        self.assertEqual(
            normalize_transcript("Vee-uh please continue"),
            "Via please continue",
        )

    def test_resume_excerpt_is_short_and_retains_remainder(self):
        text = (
            "First short sentence. Second short sentence. "
            "Third sentence contains the remaining information."
        )
        excerpt, consumed, has_more = _resume_excerpt(
            text,
            max_words=5,
        )

        self.assertEqual(excerpt, "First short sentence.")
        self.assertTrue(has_more)
        self.assertTrue(text[consumed:].strip().startswith("Second"))

    def test_resume_excerpt_caps_a_long_sentence(self):
        text = "one two three four five six seven eight nine."
        excerpt, _, has_more = _resume_excerpt(text, max_words=5)

        self.assertEqual(excerpt, "one two three four five")
        self.assertTrue(has_more)

    def test_real_question_is_not_a_confirmation(self):
        self.assertEqual(
            classify_resume_intent(
                "Can you explain the pricing instead?"
            ),
            "other",
        )

    def test_paused_topic_question_is_recognized(self):
        self.assertTrue(
            is_resume_context_request(
                "What were we talking about before?"
            )
        )
        self.assertTrue(
            is_resume_context_request("Where were we?")
        )
        self.assertFalse(
            is_resume_context_request(
                "What were we talking about in the report?"
            )
        )

    def test_topic_reminder_uses_original_query(self):
        reminder = _paused_topic_reminder(
            "Explain Qdrant and its role in Via"
        )

        self.assertIn("Explain Qdrant", reminder)
        self.assertEqual(
            reminder,
            "We were discussing: Explain Qdrant and its role in Via.",
        )

    def test_stop_discards_without_sidequest(self):
        decision = classify_interruption("stop now")
        self.assertEqual(decision.intent, "stop")
        self.assertEqual(decision.resume_policy, "discard")

    def test_backchannel_resumes_automatically(self):
        decision = classify_interruption("got it")
        self.assertEqual(decision.intent, "backchannel")
        self.assertEqual(decision.resume_policy, "automatic")

    def test_clarification_waits_for_resume_choice(self):
        decision = classify_interruption("what do you mean by that?")
        self.assertEqual(decision.intent, "clarification")
        self.assertEqual(decision.resume_policy, "confirm")

    def test_side_question_resumes_automatically(self):
        decision = classify_interruption("what is Redis used for?")
        self.assertEqual(decision.intent, "side_question")
        self.assertEqual(decision.resume_policy, "automatic")

    def test_topic_switch_discards_paused_answer(self):
        decision = classify_interruption("let's talk about deployment")
        self.assertEqual(decision.intent, "topic_switch")
        self.assertEqual(decision.resume_policy, "discard")


class PausedResponseTests(unittest.TestCase):
    def test_resume_starts_after_last_acknowledged_segment(self):
        response = PausedResponse(response_id="response-1")
        response.append_generated("First sentence. Second sentence.")
        response.register_segment("segment-1", len("First sentence. "))

        self.assertTrue(
            response.acknowledge_segment("segment-1")
        )
        response.mark_generation_complete()

        self.assertEqual(
            response.acknowledged_text,
            "First sentence. ",
        )
        self.assertEqual(
            response.remaining_text,
            "Second sentence.",
        )

    def test_unacknowledged_partial_sentence_replays(self):
        response = PausedResponse(response_id="response-1")
        response.append_generated("A partially heard sentence.")
        response.register_segment(
            "segment-1",
            len(response.generated_text),
        )

        self.assertEqual(
            response.remaining_text,
            "A partially heard sentence.",
        )


class ConversationStateTests(unittest.TestCase):
    def test_nested_paused_responses_use_lifo_order(self):
        state = ConversationState()
        first = PausedResponse(response_id="first")
        second = PausedResponse(response_id="second")

        state.begin(first)
        state.interrupt()
        state.begin(second)
        state.interrupt()

        self.assertEqual(state.resume().response_id, "second")
        state.finish("second")
        self.assertEqual(state.resume().response_id, "first")


class ProvisionalInterruptionTests(
    unittest.IsolatedAsyncioTestCase
):
    async def asyncSetUp(self):
        self.session = VoiceSession()
        self.controller = ResponseController()
        response_id = self.controller.begin()
        self.response = PausedResponse(response_id=response_id)
        self.response.append_generated(
            "This is the answer Via should continue."
        )
        self.response.mark_generation_complete()
        self.session.conversation_state.begin(self.response)
        self.session.controller = self.controller
        self.session.voice_task = asyncio.create_task(
            asyncio.sleep(1)
        )

    async def asyncTearDown(self):
        await self.session.close()

    async def test_provisional_stop_does_not_create_sidequest(self):
        response_id = (
            self.session.begin_provisional_interruption()
        )

        self.assertEqual(response_id, self.response.response_id)
        self.assertIs(
            self.session.conversation_state.current,
            self.response,
        )
        self.assertFalse(
            self.session.conversation_state.has_paused()
        )
        self.assertTrue(self.controller.cancelled)

    async def test_final_transcript_commits_interruption(self):
        self.session.begin_provisional_interruption()

        committed = self.session.commit_pending_interruption()

        self.assertIs(committed, self.response)
        self.assertIsNone(self.session.conversation_state.current)
        self.assertIs(
            self.session.conversation_state.peek_paused(),
            self.response,
        )
        self.assertIsNone(
            self.session.pending_interruption_response_id
        )

    async def test_watchdog_recovers_false_speech_start(self):
        handler = AudioHandler()
        connection = FakeConnectionManager()
        scheduled = []
        original_timeout = (
            settings.VOICE_INTERRUPTION_CONFIRM_TIMEOUT_SECONDS
        )
        settings.VOICE_INTERRUPTION_CONFIRM_TIMEOUT_SECONDS = 0.01
        handler._schedule_resume = (
            lambda session, manager, prefix: scheduled.append(prefix)
        )

        try:
            self.session.begin_provisional_interruption()
            handler._arm_interruption_watchdog(
                self.session,
                connection,
            )
            await asyncio.sleep(0.04)
        finally:
            settings.VOICE_INTERRUPTION_CONFIRM_TIMEOUT_SECONDS = (
                original_timeout
            )

        self.assertEqual(len(scheduled), 1)
        self.assertTrue(
            self.session.conversation_state.has_paused()
        )
        self.assertIsNone(
            self.session.pending_interruption_response_id
        )
        self.assertIn(
            "interruption_recovered",
            [message["type"] for message in connection.messages],
        )


class DeepgramMessageTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.events = []
        self.errors = []

        async def on_transcript(event):
            self.events.append(event)

        async def on_error(reason):
            self.errors.append(reason)

        self.provider = DeepgramStreamingSTT(
            on_transcript=on_transcript,
            on_error=on_error,
        )

    async def test_interim_and_speech_final(self):
        await self.provider._handle_message(
            {
                "type": "Results",
                "is_final": False,
                "speech_final": False,
                "channel": {
                    "alternatives": [
                        {
                            "transcript": "hello wor",
                            "confidence": 0.8,
                        }
                    ]
                },
            }
        )
        await self.provider._handle_message(
            {
                "type": "Results",
                "is_final": True,
                "speech_final": True,
                "channel": {
                    "alternatives": [
                        {
                            "transcript": "hello world",
                            "confidence": 0.95,
                        }
                    ]
                },
            }
        )

        self.assertEqual(len(self.events), 2)
        self.assertFalse(self.events[0].is_final)
        self.assertEqual(self.events[1].text, "hello world")
        self.assertTrue(self.events[1].speech_final)

    async def test_utterance_end_flushes_final_parts(self):
        await self.provider._handle_message(
            {
                "type": "Results",
                "is_final": True,
                "speech_final": False,
                "channel": {
                    "alternatives": [
                        {
                            "transcript": "one final segment",
                            "confidence": 0.9,
                        }
                    ]
                },
            }
        )
        await self.provider._handle_message(
            {"type": "UtteranceEnd"}
        )

        self.assertEqual(len(self.events), 1)
        self.assertEqual(
            self.events[0].text,
            "one final segment",
        )
        self.assertTrue(self.events[0].is_final)


if __name__ == "__main__":
    unittest.main()
