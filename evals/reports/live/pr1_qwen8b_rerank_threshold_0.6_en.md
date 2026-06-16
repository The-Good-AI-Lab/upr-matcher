# AI Pipeline Eval: costa_rica_2024

- Run ID: `pr1_qwen8b_rerank_threshold_0.6_en`
- Trace JSON: `/tmp/upr-matcher-pr1/evals/traces/live/pr1_qwen8b_rerank_threshold_0.6_en.json`
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

- Raw matches: 54
- Evaluated sources: 18
- `hit@1`: 0.3333
- `hit@3`: 0.5
- `hit@5`: 0.5
- `hit@10`: 0.5
- `recall@1`: 0.1441
- `recall@3`: 0.204
- `recall@5`: 0.2157
- `recall@10`: 0.2365
- `mrr`: 0.4167

## Reranking

- Evaluated sources: 18
- `hit@1`: 0.3333
- `hit@3`: 0.5
- `hit@5`: 0.5
- `hit@10`: 0.5
- `recall@1`: 0.1441
- `recall@3`: 0.1895
- `recall@5`: 0.2081
- `recall@10`: 0.2081
- `mrr`: 0.4074

## Timings

- `source_pdf_text_extraction`: 0.662s
- `reference_text_extraction`: 0.43s
- `reference_doc_row_extraction`: 0.401s
- `reference_embedding`: 19.086s
- `source_embedding`: 3.561s
- `semantic_candidate_matching`: 5.976s
- `reranking`: 3.63s
