# AI Pipeline Eval: costa_rica_2024

- Run ID: `offline_smoke_reranker_en`
- Trace JSON: `/home/arthur/Documents/gail/upr-matcher/evals/traces/live/offline_smoke_reranker_en.json`
- Source mode: `gold`
- Source language: `en`
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

- Raw matches: 897
- Evaluated sources: 3
- `hit@1`: 1.0
- `hit@3`: 1.0
- `hit@5`: 1.0
- `hit@10`: 1.0
- `recall@1`: 0.1696
- `recall@3`: 0.3363
- `recall@5`: 0.4196
- `recall@10`: 0.498
- `mrr`: 1.0

## Reranking

- Evaluated sources: 3
- `hit@1`: 0.6667
- `hit@3`: 0.6667
- `hit@5`: 0.6667
- `hit@10`: 0.6667
- `recall@1`: 0.15
- `recall@3`: 0.15
- `recall@5`: 0.15
- `recall@10`: 0.15
- `mrr`: 0.6667

## Timings

- `source_pdf_text_extraction`: 0.462s
- `reference_text_extraction`: 0.311s
- `reference_doc_row_extraction`: 0.307s
- `reference_embedding`: 39.067s
- `source_embedding`: 0.09s
- `semantic_candidate_matching`: 0.125s
- `reranking`: 2.241s
