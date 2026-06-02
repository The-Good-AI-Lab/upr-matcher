import os
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch

# Ensure configuration-dependent modules can initialize
os.environ.setdefault("OPENROUTER_API_KEY", "test-key")

from fmsi_un_recommendations import recommendation_processing as recommendations  # noqa: E402
from fmsi_un_recommendations import similarity_search  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data" / "sample_1"
FMSI_PDF = DATA_DIR / "fmsi_recommendations.pdf"
UN_DOCX = DATA_DIR / "upr-thematic-list.docx"


class RecommendationProcessingTests(TestCase):
    def test_read_un_recommendation_rows_extracts_data(self) -> None:
        rows = recommendations.extract_un_recommendation_rows(UN_DOCX)
        self.assertGreater(len(rows), 0)
        header = "Recommendation and recommending State"
        self.assertIn(header, rows[1])
        self.assertTrue(any("Ratify the human rights instruments" in row[header] for row in rows if header in row))

    @patch("fmsi_un_recommendations.recommendation_processing.chat_with_openrouter")
    def test_extract_fmsi_recommendations_llm(self, mock_chat: MagicMock) -> None:
        mock_chat.return_value = (
            "["
            '{"recommendation":"First recommendation","theme":"Education","domain":"Children","beneficiaries":"Students"},'
            '{"recommendation":"Second recommendation","theme":"Health","domain":"Health","beneficiaries":"Children"}'
            "]"
        )
        extracted = recommendations.extract_fmsi_pdf_recommendations(FMSI_PDF)
        self.assertEqual(len(extracted), 2)
        self.assertEqual(extracted[0].recommendation, "First recommendation")

    @patch("fmsi_un_recommendations.recommendation_processing.chat_with_openrouter")
    def test_extract_fmsi_recommendations_no_results(self, mock_chat: MagicMock) -> None:
        mock_chat.return_value = "[]"
        with self.assertRaises(ValueError):
            recommendations.extract_fmsi_pdf_recommendations(FMSI_PDF)

    @patch("fmsi_un_recommendations.recommendation_processing._chunk_text", return_value=["chunk 1", "chunk 2"])
    @patch("fmsi_un_recommendations.recommendation_processing.chat_with_openrouter")
    def test_extract_fmsi_recommendations_chunking(
        self,
        mock_chat: MagicMock,
        _: MagicMock,
    ) -> None:
        mock_chat.side_effect = [
            '[{"recommendation":"Chunk 1 recommendation","theme":"Education","domain":"Children","beneficiaries":"Students"}]',
            '[{"recommendation":"Chunk 2 recommendation","theme":"Health","domain":"Health","beneficiaries":"Children"}]',
        ]
        extracted = recommendations.extract_fmsi_pdf_recommendations(
            FMSI_PDF,
        )
        self.assertEqual(mock_chat.call_count, 2)
        self.assertEqual(
            [rec.recommendation for rec in extracted], ["Chunk 1 recommendation", "Chunk 2 recommendation"]
        )

    @patch("fmsi_un_recommendations.similarity_search.embed_texts_openrouter")
    def test_embed_recommendation_rows_attaches_embedding(
        self,
        mock_embed_texts: MagicMock,
    ) -> None:
        fake_embedding = [0.01, 0.02, 0.03]
        mock_embed_texts.return_value = [fake_embedding]

        rows_with_embeddings = similarity_search.embed_un_recommendations(
            [{"Recommendation": "Protect human rights", "State": "Italy"}]
        )

        self.assertEqual(len(rows_with_embeddings), 1)
        self.assertEqual(rows_with_embeddings[0]["embedding"], fake_embedding)
        mock_embed_texts.assert_called_once()
        self.assertEqual(mock_embed_texts.call_args.args[0], ["Recommendation: Protect human rights\nState: Italy"])

    def test_cosine_similarity(self) -> None:
        self.assertAlmostEqual(similarity_search.cosine_similarity([1.0, 0.0], [1.0, 0.0]), 1.0)
        self.assertEqual(similarity_search.cosine_similarity([0.0, 0.0], [1.0, 1.0]), 0.0)

    def test_match_recommendations(self) -> None:
        fmsi_rows = [
            {"text": "Rec A", "embedding": [1.0, 0.0]},
            {"text": "Rec B", "embedding": [0.0, 1.0]},
        ]
        un_rows = [
            {
                "Recommendation and recommending State": "UN Rec 1",
                "embedding": [0.9, 0.1],
            },
            {
                "Recommendation and recommending State": "UN Rec 2",
                "embedding": [0.1, 0.95],
            },
        ]
        matches = similarity_search.match_recommendation_vectors(fmsi_rows, un_rows, threshold=0.6)
        self.assertEqual(len(matches), 2)
        self.assertEqual({match["target_index"] for match in matches}, {0, 1})

    def test_extract_fmsi_recommendations_algo(self) -> None:
        sample_text = (
            "1.4 Recommendations\n"
            "a) Improve parental and child perceptions of the relevance of education to future goals.\n"
            "b) More awareness needs to be provided at community level.\n"
            "- Sub action continues here.\n"
            "c) Promote awareness that parental responsibilities go beyond paying fees.\n"
            "\nConclusion:\n"
            "a. Enhance the perception of education's relevance to future goals and income.\n"
        )

        extracted = recommendations.extract_fmsi_recommendations_algo(sample_text)

        self.assertGreaterEqual(len(extracted), 3)
        first_entry = extracted[0]
        self.assertIn("Improve parental and child perceptions", first_entry["text"])
        self.assertTrue(first_entry["summary"])
