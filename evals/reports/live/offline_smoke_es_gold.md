# AI Pipeline Eval: costa_rica_2024

- Run ID: `offline_smoke_es_gold`
- Trace JSON: `/home/arthur/Documents/gail/upr-matcher/evals/traces/live/offline_smoke_es_gold.json`
- Source mode: `gold`
- Source language: `es`
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

- Raw matches: 1495
- Evaluated sources: 4
- `hit@1`: 0.0
- `hit@3`: 0.5
- `hit@5`: 0.75
- `hit@10`: 0.75
- `recall@1`: 0.0
- `recall@3`: 0.1125
- `recall@5`: 0.2375
- `recall@10`: 0.3
- `mrr`: 0.2292

## Reranking

- Reranking skipped by CLI flag.

## Timings

- `source_pdf_text_extraction`: 0.433s
- `reference_text_extraction`: 0.294s
- `reference_doc_row_extraction`: 0.291s
- `reference_embedding`: 50.705s
- `source_embedding`: 0.189s
- `semantic_candidate_matching`: 0.174s
