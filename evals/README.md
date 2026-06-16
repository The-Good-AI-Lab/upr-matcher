# UPR Matcher Evaluation Framework

This directory contains the first runnable evaluation framework for the
non-deterministic UPR Matcher pipeline. It uses real documents and separates the
pipeline into stage-level checks:

1. Backend reference DOCX text extraction.
2. Backend reference DOCX row/table extraction.
3. FMSI recommendation extraction with OpenRouter.
4. Local embedding candidate retrieval.
5. Local cross-encoder reranking.
6. Trace/report generation for manual error analysis.

The current frontend uploads the original PDF/DOCX files to `/matches`; browser
handling is preview/rendering, not the AI extraction path. This runner therefore
exercises the backend extraction and matching path used by the worker.

The runner currently has direct match labels for `costa_rica_2024`. Bangladesh
and Papua New Guinea labels are weaker advocacy-impact labels, and the larger
UPR materials folder is unlabeled regression coverage.

## Runner

Run from the repository root with the backend environment:

```bash
uv run --project backend python evals/tools/run_ai_pipeline_eval.py --help
```

The runner writes:

- JSON traces to `evals/traces/live/`
- Markdown reports to `evals/reports/live/`

Traces include file hashes, settings, stage timings, extraction metrics,
retrieval/rerank metrics, top matches, and OpenRouter usage estimates. They do
not print or store the OpenRouter key.

## ML Eval Suite

The suite command assembles the current ML eval process and writes a single
summary report:

```bash
uv run --project backend python evals/tools/run_ml_eval_suite.py
```

Default mode is offline and deterministic. It uses existing Costa Rica traces,
regenerates the candidate labeling queues, summarizes human-label coverage, and
reports reranker lift from traces that already contain reranker metrics.

Outputs:

- `evals/reports/ml_eval_suite_summary.md`
- `evals/reports/ml_eval_suite_summary.json`
- `evals/reports/reranker_lift.md`
- `evals/reports/reranker_lift.json`
- `evals/reports/embedding_model_sweep.md`
- `evals/reports/embedding_model_sweep.json`
- `evals/reports/costa_rica_final_match_quality.md`
- `evals/reports/costa_rica_final_match_quality.json`
- refreshed files in `evals/labeling/`

Use these opt-in flags for the expensive or nondeterministic stages:

```bash
# Recompute local semantic retrieval baselines.
uv run --project backend python evals/tools/run_ml_eval_suite.py \
  --refresh-baselines

# Run local reranker sweeps before summarizing lift.
uv run --project backend python evals/tools/run_ml_eval_suite.py \
  --run-reranker-sweep

# Inspect an embedding-model comparison without making model calls.
uv run --project backend python evals/tools/run_ml_eval_suite.py \
  --embedding-model-sweep qwen/qwen3-embedding-8b \
  --embedding-model-sweep openai/text-embedding-3-small \
  --embedding-provider openrouter \
  --dry-run-embedding-sweep

# Compare OpenRouter embedding models on the same Costa Rica retrieval task.
uv run --project backend python evals/tools/run_ml_eval_suite.py \
  --embedding-model-sweep qwen/qwen3-embedding-8b \
  --embedding-model-sweep openai/text-embedding-3-small \
  --embedding-provider openrouter \
  --allow-openrouter-embeddings

# Spend OpenRouter budget on repeated source-extraction stability.
uv run --project backend python evals/tools/run_ml_eval_suite.py \
  --run-extraction-repeats \
  --allow-openrouter \
  --extraction-repeats 3 \
  --max-cost-usd 10
```

## Core Commands

Spanish source to English UPR matrix, using gold Costa Rica source
recommendations:

```bash
uv run --project backend python evals/tools/run_ai_pipeline_eval.py \
  --source-mode gold \
  --source-language es \
  --candidate-top-k 10 \
  --skip-reranker \
  --run-id costa_rica_full_es_gold
```

English translated source control:

```bash
uv run --project backend python evals/tools/run_ai_pipeline_eval.py \
  --source-mode gold \
  --source-language en \
  --candidate-top-k 10 \
  --skip-reranker \
  --run-id costa_rica_full_en_gold
```

Live OpenRouter extraction smoke with a $10 budget cap:

```bash
uv run --project backend python evals/tools/run_ai_pipeline_eval.py \
  --source-mode both \
  --source-language es \
  --limit-sources 5 \
  --candidate-top-k 10 \
  --skip-reranker \
  --allow-openrouter \
  --max-cost-usd 10 \
  --prompt-usd-per-1m 3 \
  --completion-usd-per-1m 3 \
  --max-llm-chunks 1 \
  --max-completion-tokens 4096 \
  --run-id live_smoke_openrouter_costa_rica
```

Reranker smoke:

```bash
uv run --project backend python evals/tools/run_ai_pipeline_eval.py \
  --source-mode gold \
  --source-language en \
  --limit-sources 3 \
  --candidate-top-k 10 \
  --reranker-top-k 5 \
  --run-id offline_smoke_reranker_en
```

## Current Baselines

These runs were produced from the current Costa Rica parser-regression traces
using direct match labels.

| Run | Stage | Sources | hit@10 | recall@10 | MRR | Notes |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `costa_rica_parser_regression_es_gold` | semantic candidates | 18 labeled sources | 0.7778 | 0.3722 | 0.3455 | Primary `es-en` condition |
| `costa_rica_parser_regression_en_gold` | semantic candidates | 18 labeled sources | 0.9444 | 0.6482 | 0.6972 | `en-en` control |
| `offline_smoke_reranker_en` | semantic candidates | 3 English sources | 1.0000 | 0.4980 | 1.0000 | Pre-rerank comparison |
| `offline_smoke_reranker_en` | reranked candidates | 3 English sources | 0.6667 | 0.1500 | 0.6667 | Reranker hurts this small sample |

Document extraction checks for Costa Rica:

- Source PDF text contains 26/27 gold Spanish source recommendations by exact normalized containment.
- Missing source ID: `costa_rica_2024:discrimination:3`.
- Raw reference text contains all 82 gold target IDs.
- Parsed DOCX rows contain all 82 gold target IDs.

Live OpenRouter extraction smoke:

- Run ID: `live_smoke_openrouter_costa_rica`
- OpenRouter calls: 1
- Estimated cost using conservative `$3/M` prompt and completion assumptions:
  `$0.042897`
- Extracted recommendations: 28
- Gold source recommendations: 27
- Gold coverage at token-similarity threshold `0.35`: `1.0`

Interpretation: this stage is non-deterministic enough that traces should be
kept with every live run. A previous smoke with the same harness grouped bullets
and only extracted 7 recommendations; the refreshed run covered the gold set.

## Interpreting Metrics

- `gold_target_id_text_coverage`: whether the target recommendation IDs exist in
  the raw reference text. This checks document text extraction.
- `gold_target_id_coverage`: whether those IDs survive table row parsing. This
  checks row extraction.
- `hit@k`: whether at least one expected target appears in the top `k`.
- `recall@k`: fraction of expected gold targets found in the top `k`.
- `precision@k`: fraction of returned top `k` targets that are gold targets.
- `MRR`: reciprocal rank of the first relevant target.
- `NDCG@k`: ranking quality with `very_similar` labels weighted above
  `similar` labels.

Use the English control to separate cross-lingual loss from general retrieval
loss. In the current baseline, `en-en` substantially outperforms `es-en`.

## Embedding Model Sweeps

PR #1 uses OpenRouter for embeddings through `EMBEDDING_MODEL`. The sweep tool
runs identical Costa Rica `es-en` and `en-en` retrieval evals while changing
only that environment variable.

Direct command:

```bash
uv run --project backend python evals/tools/compare_embedding_models.py \
  --embedding-model qwen/qwen3-embedding-8b \
  --embedding-model openai/text-embedding-3-small \
  --embedding-provider openrouter \
  --allow-openrouter-embeddings
```

The output compares hit@10, recall@10, precision@10, MRR, NDCG@10, embedding
latency, and the `en-en` minus `es-en` language gap per model. Use
`--dry-run` first to inspect the exact commands without making OpenRouter calls.
Failed model/language runs are recorded in the report while successful runs are
kept. Use `--fail-fast` when debugging a single provider failure.

## OpenRouter Budget Guard

Live calls require `--allow-openrouter`. The runner reads `backend/.env` and
uses `OPENROUTER_API_KEY`, but it never prints the key.

Cost is guarded before each call with a conservative token estimate and recorded
after the response with provider token usage when available. Pricing defaults
are intentionally configurable because OpenRouter pricing is model-specific:

```bash
--max-cost-usd 10
--prompt-usd-per-1m 3
--completion-usd-per-1m 3
```

## Next Labels To Add

1. Fill the Costa Rica candidate labeling queue so precision, false-positive
   categories, and LLM judge validation can be measured.
2. Convert Bangladesh and Papua New Guinea advocacy-impact labels into separate
   coarse retrieval checks, not direct precision/recall match labels.
3. Sample from `evals/datasets/upr_materials_document_pairs.jsonl` for
   unlabeled extraction regression tests.
