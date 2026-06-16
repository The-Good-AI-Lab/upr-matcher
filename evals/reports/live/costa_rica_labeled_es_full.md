# AI Pipeline Eval: costa_rica_2024

- Run ID: `costa_rica_labeled_es_full`
- Trace JSON: `/home/arthur/Documents/gail/upr-matcher/evals/traces/live/costa_rica_labeled_es_full.json`
- Source mode: `both`
- Source language: `es`
- OpenRouter calls: 1 (~$0.040530 estimated)

## Document Extraction

- Source text chars: 43609
- Gold source recommendation coverage in source text: 0.963
- Reference rows: 299
- Rows with target IDs: 298
- Gold target ID coverage in raw reference text: 1.0
- Gold target ID coverage in parsed rows: 0.9878

## FMSI Extraction

- LLM extracted recommendations: 7
- Expected gold recommendations: 27
- Gold coverage at similarity threshold: 0.2963
- Average best similarity: 0.3011

## Semantic Candidate Matching

- Raw matches: 8073
- Evaluated sources: 18
- `hit@1`: 0.1667
- `hit@3`: 0.5
- `hit@5`: 0.6111
- `hit@10`: 0.7778
- `recall@1`: 0.1148
- `recall@3`: 0.216
- `recall@5`: 0.2544
- `recall@10`: 0.3722
- `mrr`: 0.3455

## Reranking

- Evaluated sources: 18
- `hit@1`: 0.2222
- `hit@3`: 0.5
- `hit@5`: 0.5556
- `hit@10`: 0.5556
- `recall@1`: 0.0922
- `recall@3`: 0.1993
- `recall@5`: 0.2526
- `recall@10`: 0.2526
- `mrr`: 0.3352

## Timings

- `source_pdf_text_extraction`: 0.498s
- `reference_text_extraction`: 0.328s
- `reference_doc_row_extraction`: 0.324s
- `llm_fmsi_extraction`: 92.42s
- `reference_embedding`: 61.011s
- `source_embedding`: 1.801s
- `semantic_candidate_matching`: 0.915s
- `reranking`: 3.622s
