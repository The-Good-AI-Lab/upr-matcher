# AI Pipeline Eval: costa_rica_2024

- Run ID: `pr1_qwen8b_rerank_threshold_0.6_es`
- Trace JSON: `/tmp/upr-matcher-pr1/evals/traces/live/pr1_qwen8b_rerank_threshold_0.6_es.json`
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

- Raw matches: 1
- Evaluated sources: 18
- `hit@1`: 0.0
- `hit@3`: 0.0
- `hit@5`: 0.0
- `hit@10`: 0.0
- `recall@1`: 0.0
- `recall@3`: 0.0
- `recall@5`: 0.0
- `recall@10`: 0.0
- `mrr`: 0.0

## Reranking

- Evaluated sources: 18
- `hit@1`: 0.0
- `hit@3`: 0.0
- `hit@5`: 0.0
- `hit@10`: 0.0
- `recall@1`: 0.0
- `recall@3`: 0.0
- `recall@5`: 0.0
- `recall@10`: 0.0
- `mrr`: 0.0

## Timings

- `source_pdf_text_extraction`: 0.657s
- `reference_text_extraction`: 0.385s
- `reference_doc_row_extraction`: 0.384s
- `reference_embedding`: 15.082s
- `source_embedding`: 5.486s
- `semantic_candidate_matching`: 5.328s
- `reranking`: 0.457s
