# ML Eval Suite Summary

- Created at: `2026-06-16T19:30:34.551235+00:00`
- Suite run ID: `ml_eval_suite_20260616T193034Z_1ee8f8c9`

## Commands

- `/home/arthur/Documents/gail/upr-matcher/backend/.venv/bin/python3 /home/arthur/Documents/gail/upr-matcher/evals/tools/build_candidate_labeling_queue.py --trace /home/arthur/Documents/gail/upr-matcher/evals/traces/live/costa_rica_parser_regression_es_gold.json --trace /home/arthur/Documents/gail/upr-matcher/evals/traces/live/costa_rica_parser_regression_en_gold.json`: ok
- `/home/arthur/Documents/gail/upr-matcher/backend/.venv/bin/python3 /home/arthur/Documents/gail/upr-matcher/evals/tools/summarize_candidate_labels.py`: ok
- `/home/arthur/Documents/gail/upr-matcher/backend/.venv/bin/python3 /home/arthur/Documents/gail/upr-matcher/evals/tools/evaluate_reranker_lift.py --report /home/arthur/Documents/gail/upr-matcher/evals/reports/reranker_lift.md --json-output /home/arthur/Documents/gail/upr-matcher/evals/reports/reranker_lift.json`: ok
- `/home/arthur/Documents/gail/upr-matcher/backend/.venv/bin/python3 /home/arthur/Documents/gail/upr-matcher/evals/tools/evaluate_final_match_quality.py --max-rank 10 --report /home/arthur/Documents/gail/upr-matcher/evals/reports/costa_rica_final_match_quality.md --json-output /home/arthur/Documents/gail/upr-matcher/evals/reports/costa_rica_final_match_quality.json`: ok
- `/home/arthur/Documents/gail/upr-matcher/backend/.venv/bin/python3 /home/arthur/Documents/gail/upr-matcher/evals/tools/compare_embedding_models.py --candidate-top-k 10 --trace-root /home/arthur/Documents/gail/upr-matcher/evals/traces/live --report-root /home/arthur/Documents/gail/upr-matcher/evals/reports/live --report /home/arthur/Documents/gail/upr-matcher/evals/reports/embedding_model_sweep.md --json-output /home/arthur/Documents/gail/upr-matcher/evals/reports/embedding_model_sweep.json --embedding-model qwen/qwen3-embedding-8b --embedding-model openai/text-embedding-3-small --embedding-provider openrouter --dry-run`: ok

## Retrieval Baselines

| Pair | Run | Sources | Links | Target coverage | hit@10 | recall@10 | precision@10 | MRR | NDCG@10 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `es-en` | `costa_rica_parser_regression_es_gold` | 18 | 90 | 1 | 0.7778 | 0.3722 | 0.1333 | 0.3455 | 0.3046 |
| `en-en` | `costa_rica_parser_regression_en_gold` | 18 | 90 | 1 | 0.9444 | 0.6482 | 0.25 | 0.6972 | 0.5783 |

## Language Gap

- Recall@10 gap (`en-en` minus `es-en`): 0.276
- MRR gap (`en-en` minus `es-en`): 0.3517
- NDCG@10 gap (`en-en` minus `es-en`): 0.2737

## Human Labels

- Candidate rows: 540
- Labeled rows: 0
- Decisive rows: 0
- Precision over decisive labels: n/a
- Missed-gold rows: 111
- Reviewed missed-gold rows: 0

| Pair | Candidate rows | Labeled rows |
| --- | ---: | ---: |
| `en-en` | 270 | 0 |
| `es-en` | 270 | 0 |

## Reranker Lift

| Run | Pair | Sources | recall@10 delta | MRR delta | NDCG@10 delta |
| --- | --- | ---: | ---: | ---: | ---: |
| `costa_rica_labeled_en_full` | `en-en` | 18 | -0.3243 | -0.1509 | -0.2032 |
| `costa_rica_labeled_es_full` | `es-en` | 18 | -0.1196 | -0.0103 | -0.0708 |
| `offline_smoke_reranker_en` | `en-en` | 3 | -0.348 | -0.3333 | -0.3259 |

## Embedding Model Sweep

- Dry run only. No embedding calls were executed.

## Final Match Quality

- Policy: rank <= 10, minimum semantic score n/a
- Selected rows: 540
- Selected decisive rows: 0
- Precision: n/a
- Recall: n/a
- F1: n/a

## Extraction Stability

- Not run. Use `--run-extraction-repeats --allow-openrouter` to spend OpenRouter budget on this stage.

## Gate Status

| Stage | Status |
| --- | --- |
| Source extraction | not run in this suite; opt in with OpenRouter |
| Semantic retrieval | baseline metrics available for es-en and en-en |
| Embedding model sweep | dry run |
| Candidate precision | blocked on human labels |
| Reranker | lift report generated |
| Final match quality | metrics blocked on labels |
| LLM judge validation | blocked until enough human pass/fail labels exist |
