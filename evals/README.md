# UPR Matcher ML Evals

This directory contains the reusable ML evaluation harness for the
non-deterministic UPR Matcher pipeline.

The committed eval assets are intentionally small:

- `tools/`: runnable stage-level eval scripts.
- `gold/costa_rica_2024_*.jsonl`: direct human labels for the first eval case.
- `datasets/document_pairs.yaml`: local document names and case metadata.
- `RESULTS.md`: one consolidated record of the results collected for this PR.

Generated run artifacts are not committed. The scripts write local traces,
reports, and labeling queues under ignored directories:

- `evals/traces/`
- `evals/reports/`
- `evals/labeling/`

## Data Prerequisite

The Costa Rica eval uses local validation documents. By default the scripts look
for them at:

```text
../un-recommendations/data/fmsi-poc-data/validation/
```

Set `UPR_VALIDATION_ROOT` to override that location:

```bash
UPR_VALIDATION_ROOT=/path/to/validation \
uv run --project backend python evals/tools/run_ml_eval_suite.py
```

Live OpenRouter stages read `backend/.env` for `OPENROUTER_API_KEY`, but the
eval scripts never print the key.

## Default Suite

Run the deterministic offline suite from the repository root:

```bash
uv run --project backend python evals/tools/run_ml_eval_suite.py
```

If baseline traces are absent, the suite regenerates them before building the
local labeling queue and summary reports. Outputs remain local because the
artifact directories are ignored.

## Stage Commands

Run a gold-source Costa Rica retrieval baseline:

```bash
uv run --project backend python evals/tools/run_ai_pipeline_eval.py \
  --source-mode gold \
  --source-language es \
  --candidate-top-k 10 \
  --skip-reranker \
  --run-id costa_rica_es_gold
```

Compare OpenRouter embedding models:

```bash
uv run --project backend python evals/tools/compare_embedding_models.py \
  --embedding-model qwen/qwen3-embedding-8b \
  --embedding-model qwen/qwen3-embedding-4b \
  --embedding-provider openrouter \
  --allow-openrouter-embeddings
```

Run repeated live extraction with an explicit budget cap:

```bash
uv run --project backend python evals/tools/evaluate_extraction_stability.py \
  --source-language es \
  --repeats 3 \
  --allow-openrouter \
  --max-cost-usd 10
```

Generate a candidate labeling queue from traces:

```bash
uv run --project backend python evals/tools/build_candidate_labeling_queue.py \
  --trace evals/traces/live/costa_rica_es_gold.json \
  --trace evals/traces/live/costa_rica_en_gold.json
```

## Metrics

- `hit@k`: at least one expected target appears in the top `k`.
- `recall@k`: fraction of expected targets found in the top `k`.
- `precision@k`: fraction of returned top `k` targets that are expected.
- `MRR`: reciprocal rank of the first relevant target.
- `NDCG@k`: ranking quality with `very_similar` labels weighted above
  `similar` labels.

Report `es-en` and `en-en` separately. For Costa Rica, `es-en` is the primary
real pipeline condition and `en-en` is the translated-source control.

## Current Results

See `evals/RESULTS.md` for the consolidated PR results, including:

- Costa Rica label inventory.
- OpenRouter embedding model comparison.
- PR #1 threshold calibration results.
- Reranker lift results.
- Extraction stability results.
- Next ML evaluation steps.
