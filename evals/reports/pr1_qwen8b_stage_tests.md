# PR #1 Qwen 8B Stage Tests

These runs used PR #1's default embedding model, `qwen/qwen3-embedding-8b`.
`EMBEDDING_MODEL` was not overridden.

## Threshold Sweep

| Threshold | Pair | Raw matches | hit@10 | recall@10 | MRR | NDCG@10 |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 0.0 | `es-en` | 8073 | 0.8889 | 0.6157 | 0.6065 | 0.5618 |
| 0.0 | `en-en` | 8073 | 0.8889 | 0.6482 | 0.6574 | 0.5842 |
| 0.3 | `es-en` | 2247 | 0.9444 | 0.6342 | 0.6120 | 0.5698 |
| 0.3 | `en-en` | 5600 | 0.9444 | 0.6556 | 0.6630 | 0.5885 |
| 0.6 | `es-en` | 1 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| 0.6 | `en-en` | 52 | 0.5000 | 0.2194 | 0.4167 | 0.2722 |
| 0.7 | `es-en` | 0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| 0.7 | `en-en` | 2 | 0.0556 | 0.0037 | 0.0556 | 0.0136 |

Finding: the production `match_threshold=0.6` is not calibrated for the
OpenRouter embedding scores. It filters out nearly all Spanish candidates and
causes a severe English recall drop. A threshold around `0.3` is much safer for
this labeled case.

## Reranker

| Threshold | Pair | Semantic recall@10 | Reranked recall@10 | Delta | Semantic MRR | Reranked MRR | Delta |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.3 | `es-en` | 0.6342 | 0.5344 | -0.0998 | 0.6146 | 0.6019 | -0.0127 |
| 0.3 | `en-en` | 0.6482 | 0.5464 | -0.1018 | 0.6625 | 0.5972 | -0.0653 |
| 0.6 | `es-en` | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| 0.6 | `en-en` | 0.2365 | 0.2081 | -0.0284 | 0.4167 | 0.4074 | -0.0093 |

Finding: the OpenRouter reranker does not improve the current gold retrieval
metrics. At the usable `0.3` threshold it reduces recall by about 10 points for
both language conditions. At production `0.6`, retrieval is already too sparse
for reranking to recover.

## Extraction Stability

Run ID: `pr1_extraction_stability_default_20260616`

| Repeats | Successful | Failed | OpenRouter calls | Estimated cost |
| ---: | ---: | ---: | ---: | ---: |
| 3 | 1 | 2 | 3 | $0.142374 |

| Metric | Min | Mean | Max |
| --- | ---: | ---: | ---: |
| Extracted recommendations | 0.0 | 9.3333 | 28.0 |
| Gold coverage | 0.0 | 0.3333 | 1.0 |
| Average best similarity | 0.0 | 0.3333 | 1.0 |
| Duplicate count | 0.0 | 0.0 | 0.0 |
| Pairwise recommendation Jaccard | 0.0 | 0.3333 | 1.0 |

Failed repeats:

- Repeat 2: `JSONDecodeError: Expecting value: line 1 column 1 (char 0)`
- Repeat 3: `JSONDecodeError: Expecting property name enclosed in double quotes: line 86 column 2 (char 4380)`

Finding: extraction can succeed very well once, but it is not stable enough for
the PR as-is. Two out of three repeat calls returned malformed/non-JSON output.
This needs stricter structured-output handling, response repair/retry, or a
different extraction model before it can be a reliable production stage.

## Recommendation

Do not approve production behavior with `match_threshold=0.6` as-is. The PR
should either lower the semantic retrieval threshold, avoid hard thresholding
before top-k selection, or calibrate thresholds per embedding model.

Do not treat the reranker as a quality improvement until it is retuned or gated
by labeled metrics. Current evidence shows a recall drop.

Do not treat the current extraction prompt/model path as stable. It needs a
valid JSON retry path at minimum.
