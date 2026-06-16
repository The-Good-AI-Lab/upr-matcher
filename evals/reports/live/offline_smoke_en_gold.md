# AI Pipeline Eval: costa_rica_2024

- Run ID: `offline_smoke_en_gold`
- Trace JSON: `/home/arthur/Documents/gail/upr-matcher/evals/traces/live/offline_smoke_en_gold.json`
- Source mode: `gold`
- Source language: `en`
- OpenRouter calls: 0 (~$0.000000 estimated)

## Document Extraction

- Reference rows: 299
- Rows with target IDs: 298
- Gold target ID coverage in raw reference text: 1.0
- Gold target ID coverage in parsed rows: 0.9878

## FMSI Extraction

- Live extraction was not run for this eval.

## Semantic Candidate Matching

- Raw matches: 1495
- Evaluated sources: 4
- `hit@1`: 0.75
- `hit@3`: 1.0
- `hit@5`: 1.0
- `hit@10`: 1.0
- `recall@1`: 0.1272
- `recall@3`: 0.3147
- `recall@5`: 0.3772
- `recall@10`: 0.561
- `mrr`: 0.875

## Reranking

- Reranking skipped by CLI flag.

## Timings

- `reference_text_extraction`: 0.31s
- `reference_doc_row_extraction`: 0.32s
- `reference_embedding`: 52.369s
- `source_embedding`: 0.093s
- `semantic_candidate_matching`: 0.187s
