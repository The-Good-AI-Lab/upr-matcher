# Costa Rica Labeled Eval Metrics

Generated from labeled Costa Rica 2024 traces using real documents. Extraction metrics use all 27 gold source recommendations; retrieval and reranking metrics use the 18 source recommendations that have direct positive match labels.

| Condition | Run ID | OpenRouter cost | Source text coverage | Reference text target coverage | Parsed row target coverage |
| --- | --- | ---: | ---: | ---: | ---: |
| es-en live | `costa_rica_labeled_es_full` | $0.040530 | 0.963 | 1.0 | 0.9878 |
| en-en control | `costa_rica_labeled_en_full` | $0.000000 | 0.963 | 1.0 | 0.9878 |

## FMSI Extraction

| Condition | Live OpenRouter | Extracted recs | Gold recs | Gold coverage @0.35 | Avg best similarity |
| --- | --- | ---: | ---: | ---: | ---: |
| es-en live | yes | 7 | 27 | 0.2963 | 0.3011 |
| en-en control | no | n/a | n/a | n/a | n/a |

## Semantic Retrieval

| Condition | Sources | hit@1 | hit@3 | hit@5 | hit@10 | recall@1 | recall@3 | recall@5 | recall@10 | MRR | NDCG@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| es-en live | 18 | 0.1667 | 0.5 | 0.6111 | 0.7778 | 0.1148 | 0.216 | 0.2544 | 0.3722 | 0.3455 | 0.3046 |
| en-en control | 18 | 0.5556 | 0.7778 | 0.8889 | 0.9444 | 0.2519 | 0.375 | 0.4849 | 0.6482 | 0.6972 | 0.5783 |

## Reranking

| Condition | Sources | hit@1 | hit@3 | hit@5 | hit@10 | recall@1 | recall@3 | recall@5 | recall@10 | MRR | NDCG@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| es-en live | 18 | 0.2222 | 0.5 | 0.5556 | 0.5556 | 0.0922 | 0.1993 | 0.2526 | 0.2526 | 0.3352 | 0.2338 |
| en-en control | 18 | 0.5 | 0.6111 | 0.6111 | 0.6111 | 0.2556 | 0.2988 | 0.3239 | 0.3239 | 0.5463 | 0.3751 |

## Stage Findings

- Source PDF text extraction found 26/27 gold Spanish source recommendations by exact normalized containment.
- Missing source IDs from source text exact-containment check: `costa_rica_2024:discrimination:3`.
- Reference raw DOCX text contains 82/82 gold target IDs.
- Parsed DOCX rows contain 81/82 gold target IDs; missing parsed-row target: `120.49`.
- OpenRouter extraction for `es-en live` used 1 call and estimated $0.040530 under the configured conservative pricing.
- Semantic retrieval is much stronger in `en-en` than `es-en`: recall@10 0.6482 vs 0.3722.
- Reranking reduced recall@10 in both conditions: `es-en` 0.3722 -> 0.2526; `en-en` 0.6482 -> 0.3239.

Trace files:
- es-en live: `evals/traces/live/costa_rica_labeled_es_full.json`
- en-en control: `evals/traces/live/costa_rica_labeled_en_full.json`
