# Reranker Lift

This report compares semantic-candidate ranking against reranked candidates inside the same trace.

| Run | Pair | Sources | candidate_top_k | reranker_top_k | recall@10 sem | recall@10 rerank | delta | MRR sem | MRR rerank | delta |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `costa_rica_labeled_en_full` | `en-en` | 18 | 10 | 5 | 0.6482 | 0.3239 | -0.3243 | 0.6972 | 0.5463 | -0.1509 |
| `costa_rica_labeled_es_full` | `es-en` | 18 | 10 | 5 | 0.3722 | 0.2526 | -0.1196 | 0.3455 | 0.3352 | -0.0103 |
| `offline_smoke_reranker_en` | `en-en` | 3 | 10 | 5 | 0.498 | 0.15 | -0.348 | 1 | 0.6667 | -0.3333 |

## Full Metric Deltas

| Run | Metric | Semantic | Reranked | Delta |
| --- | --- | ---: | ---: | ---: |
| `costa_rica_labeled_en_full` | `hit@10` | 0.9444 | 0.6111 | -0.3333 |
| `costa_rica_labeled_en_full` | `recall@10` | 0.6482 | 0.3239 | -0.3243 |
| `costa_rica_labeled_en_full` | `precision@10` | 0.25 | 0.463 | 0.213 |
| `costa_rica_labeled_en_full` | `mrr` | 0.6972 | 0.5463 | -0.1509 |
| `costa_rica_labeled_en_full` | `ndcg@10` | 0.5783 | 0.3751 | -0.2032 |
| `costa_rica_labeled_es_full` | `hit@10` | 0.7778 | 0.5556 | -0.2222 |
| `costa_rica_labeled_es_full` | `recall@10` | 0.3722 | 0.2526 | -0.1196 |
| `costa_rica_labeled_es_full` | `precision@10` | 0.1333 | 0.1667 | 0.0334 |
| `costa_rica_labeled_es_full` | `mrr` | 0.3455 | 0.3352 | -0.0103 |
| `costa_rica_labeled_es_full` | `ndcg@10` | 0.3046 | 0.2338 | -0.0708 |
| `offline_smoke_reranker_en` | `hit@10` | 1 | 0.6667 | -0.3333 |
| `offline_smoke_reranker_en` | `recall@10` | 0.498 | 0.15 | -0.348 |
| `offline_smoke_reranker_en` | `precision@10` | 0.3333 | 0.6667 | 0.3334 |
| `offline_smoke_reranker_en` | `mrr` | 1 | 0.6667 | -0.3333 |
| `offline_smoke_reranker_en` | `ndcg@10` | 0.5651 | 0.2392 | -0.3259 |
