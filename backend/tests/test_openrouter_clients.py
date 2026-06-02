import os
from unittest import TestCase
from unittest.mock import patch

os.environ.setdefault("OPENROUTER_API_KEY", "test-key")

from fmsi_un_recommendations import reranker as reranker_module  # noqa: E402
from fmsi_un_recommendations.openrouter import _parse_rerank_results  # noqa: E402
from fmsi_un_recommendations.reranker import RecommendationReranker  # noqa: E402


class OpenRouterClientTests(TestCase):
    def test_parse_rerank_results_accepts_openrouter_shape(self) -> None:
        parsed = _parse_rerank_results(
            {
                "results": [
                    {"index": 2, "relevance_score": 0.91},
                    {"index": 0, "relevance_score": 0.42},
                ]
            }
        )

        self.assertEqual([result.candidate_index for result in parsed], [2, 0])
        self.assertEqual([result.relevance_score for result in parsed], [0.91, 0.42])

    @patch("fmsi_un_recommendations.reranker.rerank_openrouter")
    def test_reranker_preserves_candidate_indexes(self, mock_rerank) -> None:
        mock_rerank.return_value = _parse_rerank_results({"results": [{"index": 1, "relevance_score": 0.88}]})
        with patch.object(reranker_module.settings, "rerank_top_n", 1):
            reranker = RecommendationReranker()

            results = reranker.rerank(["protect children"], ["health care", "child protection"])

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].candidate_index, 1)
        self.assertEqual(results[0].candidate, "child protection")
        self.assertEqual(results[0].reranker_score, 0.88)
