# AI Pipeline Eval: costa_rica_2024

- Run ID: `pr1_qwen8b_threshold_0.3_es`
- Trace JSON: `/tmp/upr-matcher-pr1/evals/traces/live/pr1_qwen8b_threshold_0.3_es.json`
- Source mode: `gold`
- Source language: `es`
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

- Raw matches: 2247
- Evaluated sources: 18
- `hit@1`: 0.3889
- `hit@3`: 0.8333
- `hit@5`: 0.8889
- `hit@10`: 0.9444
- `recall@1`: 0.1996
- `recall@3`: 0.4261
- `recall@5`: 0.5508
- `recall@10`: 0.6342
- `mrr`: 0.612

## Reranking

- Reranking skipped by CLI flag.

## Timings

- `source_pdf_text_extraction`: 0.586s
- `reference_text_extraction`: 0.373s
- `reference_doc_row_extraction`: 0.358s
- `reference_embedding`: 25.536s
- `source_embedding`: 3.221s
- `semantic_candidate_matching`: 4.592s
