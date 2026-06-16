# AI Pipeline Eval: costa_rica_2024

- Run ID: `pr1_qwen8b_rerank_threshold_0.3_es`
- Trace JSON: `/tmp/upr-matcher-pr1/evals/traces/live/pr1_qwen8b_rerank_threshold_0.3_es.json`
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

- Raw matches: 2240
- Evaluated sources: 18
- `hit@1`: 0.3889
- `hit@3`: 0.8333
- `hit@5`: 0.8889
- `hit@10`: 0.9444
- `recall@1`: 0.1996
- `recall@3`: 0.4261
- `recall@5`: 0.5508
- `recall@10`: 0.6342
- `mrr`: 0.6146

## Reranking

- Evaluated sources: 18
- `hit@1`: 0.3889
- `hit@3`: 0.7778
- `hit@5`: 0.8889
- `hit@10`: 0.8889
- `recall@1`: 0.2093
- `recall@3`: 0.4398
- `recall@5`: 0.5344
- `recall@10`: 0.5344
- `mrr`: 0.6019

## Timings

- `source_pdf_text_extraction`: 0.734s
- `reference_text_extraction`: 0.451s
- `reference_doc_row_extraction`: 0.448s
- `reference_embedding`: 24.023s
- `source_embedding`: 5.462s
- `semantic_candidate_matching`: 5.461s
- `reranking`: 20.138s
