# AI Pipeline Eval: costa_rica_2024

- Run ID: `pr1_qwen8b_rerank_threshold_0.3_en`
- Trace JSON: `/tmp/upr-matcher-pr1/evals/traces/live/pr1_qwen8b_rerank_threshold_0.3_en.json`
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

- Raw matches: 5619
- Evaluated sources: 18
- `hit@1`: 0.4444
- `hit@3`: 0.8889
- `hit@5`: 0.8889
- `hit@10`: 0.8889
- `recall@1`: 0.2135
- `recall@3`: 0.4308
- `recall@5`: 0.5397
- `recall@10`: 0.6482
- `mrr`: 0.6625

## Reranking

- Evaluated sources: 18
- `hit@1`: 0.3889
- `hit@3`: 0.8333
- `hit@5`: 0.8889
- `hit@10`: 0.8889
- `recall@1`: 0.2167
- `recall@3`: 0.4487
- `recall@5`: 0.5464
- `recall@10`: 0.5464
- `mrr`: 0.5972

## Timings

- `source_pdf_text_extraction`: 0.644s
- `reference_text_extraction`: 0.391s
- `reference_doc_row_extraction`: 0.387s
- `reference_embedding`: 14.426s
- `source_embedding`: 1.465s
- `semantic_candidate_matching`: 5.626s
- `reranking`: 13.254s
