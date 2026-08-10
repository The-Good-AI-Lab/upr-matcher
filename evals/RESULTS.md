# ML Evaluation Results

This is the consolidated results record for the ML eval PR. Generated traces,
JSON reports, and labeling queues were used during analysis but are not kept in
the branch.

## What We Added

- A stage-level eval harness for source extraction, semantic retrieval,
  reranking, final match quality, embedding sweeps, extraction stability, and
  binary judge validation.
- A direct-label Costa Rica 2024 gold set with Spanish source recommendations,
  English translated source controls, and graded UPR match links.
- Parser regression coverage for Word/DOCX edge cases found in the UPR
  materials.
- A documented ML eval process that separates deterministic parser checks from
  non-deterministic model quality.

## Data Reviewed

### Costa Rica 2024

This is the only direct match-label dataset currently used for precision/recall
metrics.

- Source recommendations: 27
- Match labels: 90
- Similar labels: 69
- Very similar labels: 21
- Primary language pair: `es-en`
- Control language pair: `en-en`

The Costa Rica source PDF is Spanish. The validation workbooks provide both
Spanish and English source text, so we can separate cross-lingual retrieval loss
from general retrieval quality.

### Bangladesh 2023 And Papua New Guinea 2021

These workbooks contain advocacy-impact style labels, not direct source-to-UPR
semantic match labels.

- Bangladesh: 3 source blocks, 38 current-cycle impact links, 31 weak positives.
- Papua New Guinea: 4 source blocks, 90 current-cycle impact links, 61 weak
  positives.

Use these only for coarse impact/retrieval checks until the label semantics are
manually verified. They are not mixed into the Costa Rica direct-label metrics.

### Larger UPR Materials Folder

The extra UPR materials are useful for parser robustness and future sampling,
but they are unlabeled for match accuracy.

- Total files: 282
- Parsed cases: 90
- Source plus recommendation-matrix pairs: 55
- Detected source languages among pairs: 33 English, 19 Spanish, 3 French

This confirms we have useful non-Costa-Rica coverage, especially for language
comparison, but it does not yet provide accuracy labels.

## Parser Checks

The parser work fixed Word table cases that were blocking reliable eval inputs:

- `.doc` files that are actually DOCX zip packages are read successfully.
- True legacy OLE `.doc` files fail with an actionable conversion error.
- Theme-first tables, merged headers, duplicate headers, and right/area metadata
  rows are handled.
- Costa Rica parsed DOCX rows contain all 82 gold target IDs.
- Costa Rica raw reference text contains all 82 gold target IDs.

The source PDF text check found 26 of 27 Spanish source recommendations by exact
normalized containment. The missing exact containment case was
`costa_rica_2024:discrimination:3`.

## Baseline Retrieval

Initial local semantic retrieval baselines with direct Costa Rica labels:

| Pair | hit@10 | recall@10 | MRR | NDCG@10 | Interpretation |
| --- | ---: | ---: | ---: | ---: | --- |
| `es-en` | 0.7778 | 0.3722 | 0.3455 | 0.3046 | Primary real condition; clear cross-lingual loss |
| `en-en` | 0.9444 | 0.6482 | 0.6972 | 0.5783 | Translated-source control |

The large `en-en` over `es-en` gap means language handling is a first-class eval
dimension. We should not aggregate these conditions before diagnosing the gap.

## OpenRouter Embedding Sweep

These runs changed only the embedding model and evaluated the same Costa Rica
gold-source retrieval task.

| Model | Pair | hit@10 | recall@10 | precision@10 | MRR | NDCG@10 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `qwen/qwen3-embedding-4b` | `es-en` | 0.9444 | 0.6514 | 0.2500 | 0.6820 | 0.6069 |
| `qwen/qwen3-embedding-4b` | `en-en` | 0.8889 | 0.6334 | 0.2500 | 0.6921 | 0.5979 |
| `qwen/qwen3-embedding-8b` | `es-en` | 0.8889 | 0.6296 | 0.2389 | 0.6065 | 0.5664 |
| `qwen/qwen3-embedding-8b` | `en-en` | 0.9444 | 0.6667 | 0.2611 | 0.6630 | 0.5920 |
| `openai/text-embedding-3-large` | `es-en` | 0.8333 | 0.5715 | 0.2056 | 0.5426 | 0.4895 |
| `openai/text-embedding-3-large` | `en-en` | 0.8889 | 0.5842 | 0.2222 | 0.5700 | 0.5182 |
| `openai/text-embedding-3-small` | `es-en` | 0.8889 | 0.5309 | 0.1944 | 0.5099 | 0.4451 |
| `openai/text-embedding-3-small` | `en-en` | 0.7778 | 0.5239 | 0.2179 | 0.5139 | 0.4483 |

`qwen/qwen3-embedding-4b` was the strongest tested `es-en` model. The Gemini
embedding run failed through OpenRouter with `ValueError: No embedding data
received`.

## PR #1 Threshold Calibration

PR #1 uses OpenRouter embeddings with `qwen/qwen3-embedding-8b` by default. The
existing production `match_threshold=0.6` is not calibrated for those scores.

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

The safer threshold in this labeled case was around `0.3`. A hard threshold of
`0.6` filters out almost all Spanish candidates and sharply reduces English
recall.

## Reranker Lift

The original reranker table was invalidated during review: the harness requested
10 results, while the production wrapper silently capped the API request at 5.
The harness now sends its requested `top_n` directly and requires an explicit
`--allow-openrouter-reranker` flag. Reranker lift must be rerun before drawing a
quality conclusion.

## Extraction Stability

Repeated live extraction through OpenRouter showed a reliability problem:

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

Two of three repeats returned malformed/non-JSON output. The extraction stage
needs stricter structured-output handling, repair/retry, or a different model
before it is reliable enough as a production dependency.

## Current Interpretation

- We can now evaluate each pipeline stage separately: source extraction,
  document parsing, embedding retrieval, reranking, final match policy, and
  future judge alignment.
- The strongest immediate ML issue is threshold calibration for the embedding
  model used in PR #1.
- The second issue is extraction stability: one good live run is not enough for
  release confidence.
- The third issue is labels. Costa Rica is enough to start stage evaluation, but
  it is not enough for broad product-level claims.

## Recommended Next Steps

1. Keep generated traces/reports out of commits and use this file for PR-level
   results.
2. Calibrate matching around top-k retrieval or a lower threshold before using
   OpenRouter embeddings in production.
3. Add JSON repair/retry or structured output support for extraction.
4. Label the generated Costa Rica candidate queue to measure precision and
   false-positive categories.
5. Add 3-5 more direct-label document pairs, prioritizing Spanish and other
   non-English sources.
