import os
from unittest import TestCase
from unittest.mock import MagicMock, patch

os.environ.setdefault("OPENROUTER_API_KEY", "test-key")

from fmsi_un_recommendations import openrouter as openrouter_module  # noqa: E402
from fmsi_un_recommendations import reranker as reranker_module  # noqa: E402
from fmsi_un_recommendations.openrouter import (
    _parse_rerank_results,  # noqa: E402
    rerank_openrouter,  # noqa: E402
)
from fmsi_un_recommendations.reranker import RecommendationReranker  # noqa: E402


class OpenRouterClientTests(TestCase):
    def test_rerank_retries_transient_response_read_errors(self) -> None:
        for error in (TimeoutError("timed out"), ConnectionResetError("reset")):
            with self.subTest(error=type(error).__name__):
                failed_response = MagicMock()
                failed_response.__enter__.return_value.read.side_effect = error
                successful_response = MagicMock()
                successful_response.__enter__.return_value.read.return_value = b'{"results": []}'

                with (
                    patch.object(
                        openrouter_module,
                        "urlopen",
                        side_effect=[failed_response, successful_response],
                    ) as mock_urlopen,
                    patch.object(openrouter_module.time, "sleep") as mock_sleep,
                ):
                    results = rerank_openrouter("query", ["candidate"])

                self.assertEqual(results, [])
                self.assertEqual(mock_urlopen.call_count, 2)
                mock_sleep.assert_called_once_with(1.0)

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
