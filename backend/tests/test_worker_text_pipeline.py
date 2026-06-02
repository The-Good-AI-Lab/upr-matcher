import json
import os
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

os.environ.setdefault("OPENROUTER_API_KEY", "test-key")

import fmsi_un_recommendations.db as db_module  # noqa: E402
from fmsi_un_recommendations.db import get_database  # noqa: E402
from fmsi_un_recommendations.openrouter import RerankApiResult  # noqa: E402
from fmsi_un_recommendations.settings import Settings  # noqa: E402
from fmsi_un_recommendations.worker import _build_matches, _execute_job  # noqa: E402


class WorkerTextPipelineTests(TestCase):
    @patch("fmsi_un_recommendations.reranker.rerank_openrouter")
    @patch("fmsi_un_recommendations.similarity_search.embed_texts_openrouter")
    @patch("fmsi_un_recommendations.recommendation_processing.chat_with_openrouter")
    def test_build_matches_accepts_markdown_and_json_rows(
        self,
        mock_chat,
        mock_embed,
        mock_rerank,
    ) -> None:
        mock_chat.return_value = (
            '[{"recommendation":"Protect children in law.",'
            '"theme":"Children","domain":"Child protection","beneficiaries":"Children"}]'
        )
        mock_embed.side_effect = [
            [[1.0, 0.0], [0.0, 1.0]],
            [[1.0, 0.0]],
        ]
        mock_rerank.return_value = [RerankApiResult(candidate_index=0, relevance_score=0.97)]

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_path = temp_path / "fmsi.md"
            reference_path = temp_path / "upr_rows.json"
            source_path.write_text("## Recommendations\n\n- Protect children in law.", encoding="utf-8")
            reference_path.write_text(
                json.dumps(
                    [
                        {
                            "Theme": "Children",
                            "Recommendation and recommending State": "Protect children in law.",
                        },
                        {
                            "Theme": "Health",
                            "Recommendation and recommending State": "Improve hospitals.",
                        },
                    ]
                ),
                encoding="utf-8",
            )

            embedded_un, embedded_fmsi, matches, recommendations = _build_matches(
                reference_path,
                source_path,
                threshold=0.6,
            )

        self.assertEqual(len(embedded_un), 2)
        self.assertEqual(len(embedded_fmsi), 1)
        self.assertEqual(len(recommendations), 1)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["target_index"], 0)
        self.assertEqual(matches[0]["reranker_score"], 0.97)

    @patch("fmsi_un_recommendations.reranker.rerank_openrouter")
    @patch("fmsi_un_recommendations.similarity_search.embed_texts_openrouter")
    @patch("fmsi_un_recommendations.recommendation_processing.chat_with_openrouter")
    def test_execute_job_processes_db_text_without_saved_files(
        self,
        mock_chat,
        mock_embed,
        mock_rerank,
    ) -> None:
        mock_chat.return_value = (
            '[{"recommendation":"Protect children in law.",'
            '"theme":"Children","domain":"Child protection","beneficiaries":"Children"}]'
        )
        mock_embed.side_effect = [
            [[1.0, 0.0], [0.0, 1.0]],
            [[1.0, 0.0]],
        ]
        mock_rerank.return_value = [RerankApiResult(candidate_index=0, relevance_score=0.97)]

        with tempfile.TemporaryDirectory() as temp_dir:
            previous_instance = db_module._DB_INSTANCE
            db_module._DB_INSTANCE = None
            try:
                os.environ["LOCAL_DB_PATH"] = str(Path(temp_dir) / "recommendations.db")
                db = get_database(Settings())
                db.create_job(
                    job_id="job-db-text-test",
                    user_email=None,
                    source_filename="fmsi.pdf",
                    reference_filename="upr.docx",
                    source_text="## Recommendations\n\n- Protect children in law.",
                    reference_rows=[
                        {
                            "Theme": "Children",
                            "Recommendation and recommending State": "Protect children in law.",
                        },
                        {
                            "Theme": "Health",
                            "Recommendation and recommending State": "Improve hospitals.",
                        },
                    ],
                )

                _execute_job("job-db-text-test")

                job = db.get_job("job-db-text-test")
                self.assertIsNotNone(job)
                assert job is not None
                self.assertEqual(job.status, "completed")
                self.assertIsNotNone(job.prediction_id)
                assert job.prediction_id is not None
                prediction = db.get_prediction(job.prediction_id)
                self.assertIsNotNone(prediction)
                assert prediction is not None
                self.assertIsNone(prediction.input_fmsi_path)
                self.assertIsNone(prediction.input_un_path)
                self.assertEqual(len(prediction.matches), 1)
            finally:
                os.environ.pop("LOCAL_DB_PATH", None)
                db_module._DB_INSTANCE = previous_instance
