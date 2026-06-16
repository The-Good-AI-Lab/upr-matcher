# AI Pipeline Eval: costa_rica_2024

- Run ID: `pr1_qwen8b_threshold_0.7_en`
- Trace JSON: `/tmp/upr-matcher-pr1/evals/traces/live/pr1_qwen8b_threshold_0.7_en.json`
- Source mode: `gold`
- Source language: `en`
- Embedding model: `qwen/qwen3-embedding-8b`
- Embedding provider: `openrouter`
- OpenRouter calls: 0 (~$0.000000 estimated)

## Document Extraction

- Source text chars: 43609
- Gold source recommendation coverage in source text: 0.963
- Reference rows: 299
- Rows with target IDs: 298
- Gold target ID coverage in raw reference text: 1.0
- Gold target ID coverage in parsed rows: 0.9878

## FMSI Extraction

- Live extraction was not run for this eval.

## Semantic Candidate Matching

- Raw matches: 2
- Evaluated sources: 18
- `hit@1`: 0.0556
- `hit@3`: 0.0556
- `hit@5`: 0.0556
- `hit@10`: 0.0556
- `recall@1`: 0.0037
- `recall@3`: 0.0037
- `recall@5`: 0.0037
- `recall@10`: 0.0037
- `mrr`: 0.0556

## Reranking

- Reranking skipped by CLI flag.

## Timings

- `source_pdf_text_extraction`: 0.708s
- `reference_text_extraction`: 0.43s
- `reference_doc_row_extraction`: 0.416s
- `reference_embedding`: 18.647s
- `source_embedding`: 2.41s
- `semantic_candidate_matching`: 5.73s
