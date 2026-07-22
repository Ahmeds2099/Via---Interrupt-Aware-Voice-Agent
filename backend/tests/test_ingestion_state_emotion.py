import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.document_ingestion import DocumentIngestionService
from app.services.domain_classifier import DomainClassifier
from app.services.emotion.provider import Emotion2VecProvider, EmotionResult
from app.services.session_repository import SessionRepository
from app.services.qdrant_service import QdrantService


class OptionalDocumentContextTests(unittest.TestCase):
    @patch("app.services.qdrant_service.client.query_points")
    def test_empty_document_context_skips_collection_search(self, query_points):
        results = QdrantService.search(
            [0.0] * 384,
            document_ids=[],
        )

        self.assertEqual(results, [])
        query_points.assert_not_called()


class DocumentIngestionTests(unittest.TestCase):
    def setUp(self):
        self.service = DocumentIngestionService()
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)

    def tearDown(self):
        self.directory.cleanup()

    def test_csv_preserves_rows_and_headers(self):
        path = self.root / "listings.csv"
        path.write_text(
            'address,price,notes\n"1 Main St","250000","Two bed"\n',
            encoding="utf-8",
        )

        source_type, chunks = self.service.prepare(path, path.name)

        self.assertEqual(source_type, "csv")
        self.assertEqual(chunks[0].location_type, "row")
        self.assertEqual(chunks[0].location_value, "2")
        self.assertIn("address: 1 Main St", chunks[0].text)
        self.assertIn("price: 250000", chunks[0].text)

    def test_json_preserves_nested_paths(self):
        path = self.root / "policy.json"
        path.write_text(
            json.dumps({"policy": {"limits": [1000, 2000]}}),
            encoding="utf-8",
        )

        source_type, chunks = self.service.prepare(path, path.name)

        self.assertEqual(source_type, "json")
        locations = {chunk.location_value for chunk in chunks}
        self.assertIn("$.policy.limits[0]", locations)
        self.assertIn("$.policy.limits[1]", locations)

    def test_malformed_json_is_rejected(self):
        path = self.root / "broken.json"
        path.write_text('{"missing":', encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "invalid"):
            self.service.prepare(path, path.name)

    def test_empty_csv_is_rejected(self):
        path = self.root / "empty.csv"
        path.write_text("header\n", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "No readable text"):
            self.service.prepare(path, path.name)


class DomainClassifierTests(unittest.TestCase):
    def test_real_estate_keyword_fallback(self):
        classifier = DomainClassifier()
        with patch("app.services.domain_classifier.settings.GROQ_API_KEY", ""):
            profile = classifier.classify(
                "listings.csv",
                "property address bedroom price real estate listing",
            )

        self.assertEqual(profile.domain, "real_estate")
        self.assertEqual(
            profile.professional_role,
            "real-estate professional",
        )
        self.assertEqual(profile.safety_category, "financial")

    def test_groq_real_estate_cannot_be_marked_low_risk(self):
        response = type(
            "Response",
            (),
            {
                "choices": [
                    type(
                        "Choice",
                        (),
                        {
                            "message": type(
                                "Message",
                                (),
                                {
                                    "content": json.dumps(
                                        {
                                            "domain": "Real Estate",
                                            "professional_role": "Property advisor",
                                            "description": "Listings",
                                            "confidence": 0.9,
                                            "safety_category": "general",
                                        }
                                    )
                                },
                            )()
                        },
                    )()
                ]
            },
        )()
        client = type(
            "Client",
            (),
            {
                "chat": type(
                    "Chat",
                    (),
                    {
                        "completions": type(
                            "Completions",
                            (),
                            {"create": lambda self, **kwargs: response},
                        )()
                    },
                )()
            },
        )()

        with patch("groq.Groq", return_value=client):
            profile = DomainClassifier._classify_with_groq(
                "listings.csv",
                "property listings",
            )

        self.assertEqual(profile.safety_category, "financial")


class EmotionPolicyTests(unittest.TestCase):
    def test_bilingual_model_label_normalizes_to_english(self):
        self.assertEqual(
            Emotion2VecProvider._normalize_label("生气/angry"),
            "angry",
        )

    def test_explicit_confusion_triggers_clarification(self):
        provider = Emotion2VecProvider()
        result = provider.enrich(
            EmotionResult(
                label="neutral",
                confidence=0.8,
                status="ready",
            ),
            "I am confused and do not understand this",
            0.95,
        )

        self.assertTrue(result.clarification_mode)
        self.assertGreaterEqual(result.doubt_score, 0.85)

    def test_emotion_alone_does_not_overstate_doubt(self):
        provider = Emotion2VecProvider()
        result = provider.enrich(
            EmotionResult(
                label="sad",
                confidence=0.5,
                status="ready",
            ),
            "Please explain the next item",
            0.95,
        )

        self.assertFalse(result.clarification_mode)

    def test_explicit_understanding_overrides_noisy_stress(self):
        provider = Emotion2VecProvider()
        result = provider.enrich(
            EmotionResult(
                label="angry",
                raw_label="angry",
                display_label="stressed",
                confidence=0.91,
                reliable=True,
                status="ready",
            ),
            "Okay, I understand",
            0.95,
        )

        self.assertEqual(result.display_label, "neutral")
        self.assertEqual(result.doubt_score, 0.0)
        self.assertFalse(result.clarification_mode)

    def test_repeated_reliable_stress_is_smoothed(self):
        provider = Emotion2VecProvider()
        result, history = provider.smooth(
            EmotionResult(
                label="angry",
                raw_label="angry",
                display_label="stressed",
                confidence=0.9,
                reliable=True,
                status="ready",
            ),
            [{"label": "stressed", "confidence": 0.82}],
        )

        self.assertEqual(result.display_label, "stressed")
        self.assertEqual(len(history), 2)
        self.assertGreater(result.smoothed_confidence, 0.8)


class SessionRepositoryTests(unittest.TestCase):
    def test_upstash_state_round_trip_and_separate_ttls(self):
        repository = SessionRepository()
        repository.url = "https://example.test"
        repository.token = "token"
        commands = []

        def command(payload):
            commands.append(payload)
            return "OK"

        repository._command = command
        repository.save(
            "client-1",
            {
                "messages": [{"role": "user", "content": "hello"}],
                "memories": [{"memory_id": "m1", "text": "likes tea"}],
            },
        )

        self.assertEqual(commands[0][-1], repository.SESSION_TTL_SECONDS)
        self.assertEqual(commands[1][-1], repository.MEMORY_TTL_SECONDS)
        self.assertIn("via:session:client-1", commands[0])
        self.assertIn("via:memories:client-1", commands[1])

    def test_missing_credentials_uses_memory_fallback(self):
        repository = SessionRepository()
        repository.url = ""
        repository.token = ""
        repository.save("client-2", {"messages": [], "memories": []})

        state = repository.load("client-2")

        self.assertEqual(state["client_id"], "client-2")
        self.assertEqual(repository.status["status"], "degraded")


if __name__ == "__main__":
    unittest.main()
