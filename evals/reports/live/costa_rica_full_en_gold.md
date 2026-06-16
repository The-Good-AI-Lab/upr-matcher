# AI Pipeline Eval: costa_rica_2024

- Run ID: `costa_rica_full_en_gold`
- Trace JSON: `/home/arthur/Documents/gail/upr-matcher/evals/traces/live/costa_rica_full_en_gold.json`
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

- Raw matches: 8073
- Evaluated sources: 18
- `hit@1`: 0.5556
- `hit@3`: 0.7778
- `hit@5`: 0.8889
- `hit@10`: 0.9444
- `recall@1`: 0.2519
- `recall@3`: 0.375
- `recall@5`: 0.4849
- `recall@10`: 0.6482
- `mrr`: 0.6972

## Reranking

- Reranking skipped by CLI flag.

## Timings

- `source_pdf_text_extraction`: 0.476s
- `reference_text_extraction`: 0.32s
- `reference_doc_row_extraction`: 0.316s
- `reference_embedding`: 40.402s
- `source_embedding`: 0.652s
- `semantic_candidate_matching`: 0.958s
