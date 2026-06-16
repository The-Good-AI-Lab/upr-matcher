# AI Evaluation Plan - UPR Matcher

For the focused ML quality plan, use
[`docs/ML_EVALUATION_PLAN.md`](ML_EVALUATION_PLAN.md). This broader document
also covers deterministic extraction, API, UI, and operational checks that
support reliable evals but are not themselves ML quality measurements.

This document is a starting plan for evaluating the non-deterministic parts of
UPR Matcher. It is written for the approved OpenRouter pipeline:

```text
PDF/DOCX selected in browser
  -> /matches multipart upload
  -> backend PDF/DOCX extraction
  -> FMSI recommendation extraction with OpenRouter
  -> local embeddings
  -> semantic candidate matching
  -> local cross-encoder reranking
  -> persisted prediction and UI review
```

The goal is not to create one broad "AI quality score". The goal is to evaluate
each pipeline stage independently, use deterministic checks wherever possible,
and use validated LLM judges only for criteria that require interpretation.

## Runnable Framework

The first runnable framework lives in:

```text
evals/tools/run_ai_pipeline_eval.py
evals/README.md
```

It currently evaluates `costa_rica_2024` with real documents and the normalized
gold labels under `evals/gold/`. It writes JSON traces to
`evals/traces/live/` and Markdown reports to `evals/reports/live/`.

Implemented checks:

- Raw backend reference text coverage for gold UPR target IDs.
- Parsed backend DOCX row coverage for gold UPR target IDs.
- Live OpenRouter FMSI extraction with an explicit dollar budget cap.
- Local embedding semantic retrieval metrics: hit@k, recall@k, precision@k, MRR,
  and NDCG@k.
- Local cross-encoder reranker metrics on top semantic candidates.
- `es-en` vs `en-en` language comparison using Costa Rica Spanish source text
  and English translated source text.

Initial 2026-06-15 baselines:

| Run | Stage | Condition | hit@10 | recall@10 | MRR |
| --- | --- | --- | ---: | ---: | ---: |
| `costa_rica_full_es_gold` | semantic candidates | `es-en` | 0.7778 | 0.3722 | 0.3455 |
| `costa_rica_full_en_gold` | semantic candidates | `en-en` | 0.9444 | 0.6482 | 0.6972 |
| `offline_smoke_reranker_en` | reranked candidates | `en-en`, 3-source smoke | 0.6667 | 0.1500 | 0.6667 |

The refreshed live OpenRouter extraction smoke (`live_smoke_openrouter_costa_rica`)
used one OpenRouter call with an estimated cost of `$0.042897` under conservative
`$3/M` prompt and completion assumptions. It extracted 28 recommendations versus
27 gold source recommendations, with 1.0 gold coverage at token-similarity
threshold 0.35.

The Costa Rica source PDF text extraction contains 26/27 gold Spanish source
recommendations by exact normalized containment. Missing source ID:
`costa_rica_2024:discrimination:3`.

The Costa Rica parser regression runs contain all 82 gold target IDs in raw
DOCX text and all 82 in parsed rows. The previous parsed-row miss for `120.49`
is fixed in `costa_rica_parser_regression_es_gold` and
`costa_rica_parser_regression_en_gold`.

## Principles

1. Start with error analysis on full traces before locking in metrics.
2. Evaluate stages separately so failures can be attributed to the right step.
3. Prefer code-based checks for objective failures: schema, counts, parseability,
   row IDs, text spans, empty outputs, duplicate outputs, and numeric metrics.
4. Use binary LLM judges only for subjective or semantic questions.
5. Validate every LLM judge against human labels with TPR/TNR before using it as
   a regression signal.
6. Keep live model outputs as trace artifacts so model drift and prompt changes
   are auditable.

## Trace And Dataset Foundation

Every eval run should write a trace record with enough data to reproduce and
review the run.

Required trace fields:

| Field | Purpose |
| --- | --- |
| `trace_id` | Stable ID for the run |
| `dataset_case_id` | Links the run to the input document pair |
| `source_file_sha256` | Detects source PDF changes |
| `reference_file_sha256` | Detects UPR DOCX changes |
| `model` | FMSI extraction model |
| `embedding_model` | Embedding model used for candidate retrieval |
| `reranker_model` | Reranking model |
| `settings` | Thresholds, top-k limits, chunk size, prompt version |
| `browser_extraction` | Extracted PDF markdown and UPR rows |
| `fmsi_extraction` | Raw LLM response and parsed recommendations |
| `embeddings` | Counts, dimensions, and optional vector hashes |
| `candidate_matches` | Pre-rerank candidate pairs and scores |
| `reranked_matches` | Final pairs and reranker scores |
| `prediction_id` | Stored prediction, when available |
| `timing` | Per-stage latency |
| `cost` | Tokens/request cost, when available |
| `errors` | Any exception or fallback path |

Suggested repo layout:

```text
evals/
  datasets/
    document_pairs.yaml
  gold/
    fmsi_recommendations.jsonl
    upr_rows.jsonl
    match_links.jsonl
  traces/
    live/
  reports/
  judges/
```

Initial seed data:

| Case | Source | Reference | Purpose |
| --- | --- | --- | --- |
| `vanuatu_2023` | `../un-recommendations/data/UPR Vanuatu_2023.pdf` | `../un-recommendations/data/upr46-vanuatu-thematic-list-of-recommendations.docx` | First live smoke and baseline case |

Existing validation data outside the repo:

```text
../un-recommendations/data/fmsi-poc-data/validation/
```

This directory contains document pairs and validation spreadsheets for
Bangladesh, Costa Rica, and Papua New Guinea. These are not yet normalized into
repo eval fixtures, but they are the best starting point for gold labels.

| Case | Files | Label usefulness |
| --- | --- | --- |
| Bangladesh 2023 | `2023_UPR Bangladesh.pdf`, `Summary of the stakeholders_Bangladesh_2023.pdf`, `Matrix of recommendations_Bangladesh_2023.doc`, `UPR Advocacy Evaluation Bangladesh.xlsx` | Advocacy evaluation matrix with proposed recommendations and cycle recommendations by theme/state |
| Costa Rica 2024 | `2024_UPR Costa Rica.pdf`, `Summary of the stakeholders_CostaRica_2024.pdf`, `Matrix of recommendations_CostaRica_2024.docx`, `Tabla de Recomendaciones_Costa Rica_ENG.xlsx` | Clearest match-label source: columns for similar and very similar UPR recommendations |
| Papua New Guinea 2021 | `2021_UPR PapuaNewGuinea.pdf`, `Summary of the stakeholders_PapuaNewGuinea_2021.pdf`, `Matrix of recommendations_PapuaNewGuinea_2021.docx`, `1. Advocacy Plan _ Evaluation table UPR PNG.xlsx` | Advocacy evaluation matrix with proposed recommendations and cycle recommendations by theme/state |

The first normalization target should be Costa Rica because the spreadsheet has
explicit `Similar recommendation` and `Very similar recommendation` columns.
Convert it into `evals/gold/match_links.jsonl` with fields such as:

```json
{
  "case_id": "costa_rica_2024",
  "theme": "RIGHT TO EDUCATION",
  "source_recommendation": "...",
  "target_recommendation": "...",
  "relevance": "very_similar",
  "language": "en"
}
```

Bangladesh and Papua New Guinea should be treated as semi-structured gold data
until we verify how each workbook encodes similarity and lobbying/reach status.

Add more document pairs before treating aggregate metrics as meaningful. The
first target should be 20-30 diverse document pairs or about 100 full traces,
whichever comes first.

## Human Labeling

Before building automated judges, review traces manually.

Process:

1. Run the pipeline on a mixed sample of real and synthetic cases.
2. Review 30-50 full traces with a domain reviewer.
3. Mark each trace Pass or Fail and note the first thing that went wrong.
4. Group failures into 5-10 concrete categories.
5. Label the full sample against those categories.
6. Only then create code checks or LLM judges for high-impact categories.

Gold labels to collect:

| Artifact | Human label |
| --- | --- |
| FMSI source document | Each true recommendation, source span, theme, beneficiaries |
| UPR document | Canonical row IDs, recommendation text, theme/domain/status fields |
| Match links | FMSI recommendation ID -> relevant UPR row IDs, with optional relevance grade |
| Final prediction | Correct/incorrect per returned match and missing expected matches |

Use balanced labels when validating judges. For each judge, aim for about 50
Pass and 50 Fail examples. Split labels into train/dev/test; use train examples
only as few-shot examples, tune on dev, and report final TPR/TNR on test.

## Language Dimension

Language must be tracked as a first-class evaluation dimension. Costa Rica is the
first example: the source PDF is Spanish, the UPR matrix is English, and the
validation spreadsheets provide both Spanish and English labels. That lets us
compare at least two useful conditions:

| Condition | Meaning | Use |
| --- | --- | --- |
| `es-en` | Spanish source recommendation -> English UPR row | Primary real pipeline condition for Costa Rica |
| `en-en` | English translated source recommendation -> English UPR row | Control condition to isolate cross-lingual retrieval/rerank loss |

When reporting retrieval, rerank, and final-match metrics, break results down by
`language_pair` before aggregating. If `en-en` succeeds and `es-en` fails, the
problem is likely cross-lingual semantic matching rather than the gold labels or
UPR row extraction. If both fail, inspect candidate retrieval, thresholds, and
reranking logic.

## Stage Evaluation Matrix

### 1. Backend Source PDF Text Extraction

Scope:

- `read_text_file` for PDF files in `backend/fmsi_un_recommendations/utils.py`.
- Converts uploaded source PDFs into text for the FMSI extraction prompt.

Primary risks:

- Empty extraction.
- Missing pages or damaged text order.
- Excessive whitespace normalization that damages recommendation bullets.
- Source recommendations present in raw PDF but absent from extracted text.

Code-based checks:

| Check | Method |
| --- | --- |
| Non-empty output | Extracted source text has non-whitespace content |
| Known snippet coverage | Assert known source strings appear after normalization |
| Gold source coverage | For labeled cases, check gold source recommendations or key spans against extracted text |
| Stable extraction | Snapshot normalized text hash for fixed fixtures |
| Text size bounds | Catch accidental truncation or duplicated extraction |

Metrics:

- PDF text extraction success rate.
- Known-snippet recall.
- Gold source text coverage for labeled fixtures.
- Text length variance across dependency/runtime versions.

Automation level:

- Backend unit tests for fixed fixture PDFs.
- Live eval trace field in `run_ai_pipeline_eval.py`.

### 2. Backend Reference DOCX Row Extraction

Scope:

- `extract_un_recommendation_rows` and `docx_tables_to_json` in the backend.
- Converts uploaded UPR DOCX tables into row dictionaries used for embeddings and matching.

Primary risks:

- Dropped rows.
- Wrong headers.
- Theme section rows not propagated.
- Empty cells or merged cells mishandled.
- Raw DOCX text contains a recommendation ID that the row parser drops.

Code-based checks:

| Check | Method |
| --- | --- |
| Exact or expected row count | Fixture expected row count where stable |
| Required columns | Assert recommendation, theme/domain, and status columns exist |
| Target ID coverage in raw text | Gold target IDs appear in backend raw DOCX text |
| Target ID coverage in parsed rows | Gold target IDs survive table parsing |
| No blank recommendation rows | Reject rows with no recommendation text |
| Duplicate row IDs | Report duplicate target recommendation IDs |

Metrics:

- Row-count stability.
- Required-field completeness.
- Gold target ID coverage in raw text and parsed rows.

Automation level:

- Backend unit tests for representative DOCX fixtures.
- Live eval trace fields in `run_ai_pipeline_eval.py`.

### 3. Multipart Job API Contract

Scope:

- `/matches` multipart request validation and job enqueue.
- Upload persistence and worker pickup.

Primary risks:

- API contract drift.
- Missing PDF/DOCX accepted.
- Uploads persisted with wrong file paths.
- Worker cannot consume the enqueued file paths.

Code-based checks:

| Check | Method |
| --- | --- |
| Multipart validation | Valid PDF+DOCX returns `job_id`; bad payload returns 4xx |
| File role detection | One PDF is assigned to `fmsi_pdf`, one DOC/DOCX to `un_doc` |
| Queue record integrity | Job row has source and reference file paths |
| No silent data loss | Worker can consume the exact enqueued files |

Metrics:

- API validation pass rate.
- Job enqueue success rate.
- Worker claim latency.

Automation level:

- FastAPI `TestClient` tests with mocked worker dependencies.
- Browser E2E file-upload smoke for UI contract, progress, and result rendering.

### 4. FMSI Recommendation Extraction

Scope:

- `extract_fmsi_text_recommendations`.
- LLM extracts structured recommendations from source document text.

Primary risks:

- Missing true recommendations.
- Invented recommendations.
- Paraphrased text when exact source citation is required.
- Wrong theme or beneficiaries.
- Duplicate recommendations.
- Invalid JSON or schema drift.
- Run-to-run instability.

Code-based checks:

| Check | Method |
| --- | --- |
| JSON parseability | Raw response must parse after markdown fence stripping |
| Schema validity | Every item validates as `Recommendation` |
| Theme vocabulary | Theme is in the allowed set |
| Non-empty fields | Recommendation, domain, beneficiaries, theme are non-empty |
| Grounded quote candidate | Recommendation text appears in source or passes fuzzy span match |
| Duplicate rate | Normalized recommendation text is unique |

Gold-label metrics:

| Metric | Meaning |
| --- | --- |
| Extraction recall | Fraction of human-labeled recommendations recovered |
| Extraction precision | Fraction of extracted recommendations judged real |
| Count error | Absolute difference from human count |
| Theme accuracy | Fraction with correct human-labeled theme |
| Beneficiary accuracy | Fraction with correct beneficiary label |
| Quote grounding pass rate | Fraction directly supported by source text |

LLM judges, only after human labels exist:

| Judge | Binary criterion |
| --- | --- |
| Recommendation is grounded | Pass if the extracted recommendation is explicitly supported by the source text |
| Recommendation is complete | Pass if the extracted text includes the full advocacy ask, not only a fragment |
| Theme is appropriate | Pass if the chosen theme matches the recommendation content |

Run protocol:

- Run each live extraction case 3-5 times when measuring non-determinism.
- Store raw model responses.
- Report mean, min, max, and disagreement examples.
- Pin model identifiers in traces.

### 5. Embedding Generation

Scope:

- `embed_un_recommendations`.
- `embed_fmsi_recommendations`.
- OpenRouter embedding calls in the approved PR.

Primary risks:

- Provider errors or partial responses.
- Embedding count mismatch.
- Index order mismatch.
- Vector dimension changes after model switch.
- Silent model drift.

Code-based checks:

| Check | Method |
| --- | --- |
| Count preservation | Number of embeddings equals number of input rows |
| Index preservation | Embeddings map back to the original input order |
| Dimension consistency | All vectors have the expected dimension |
| Numeric validity | No NaN, infinity, or empty vectors |
| Model traceability | Trace stores embedding model ID |

Retrieval metrics:

| Metric | Meaning |
| --- | --- |
| Recall@k | Relevant UPR row appears in top k semantic candidates |
| MRR | First relevant row appears early |
| Threshold recall | Relevant pair survives the configured cosine threshold |
| Candidate set size | Number of pairs passed to reranker |

Automation level:

- Unit tests with mocked embedding responses for ordering and shape.
- Live retrieval eval over human-labeled match links.
- Threshold sweep report for `match_threshold`.

### 6. Semantic Candidate Matching

Scope:

- `match_recommendation_vectors`.
- All-pairs cosine similarity and threshold filtering.

Primary risks:

- True links filtered out before reranking.
- Too many candidates sent to rerank.
- Score sorting regressions.
- Missing source/target row metadata.

Code-based checks:

| Check | Method |
| --- | --- |
| Cosine invariants | Identical vectors score 1; orthogonal vectors score 0 |
| Sort order | Results sorted descending by score |
| Metadata preservation | Source/target indices and text fields preserved |
| Threshold behavior | Boundary cases at, below, and above threshold |

Metrics:

- Recall@5, Recall@10, Recall@30 before rerank.
- Threshold recall.
- Average candidates per FMSI recommendation.
- Max candidates per FMSI recommendation.

Decision rule:

- This stage should optimize for recall. A false negative here cannot be
  recovered by the reranker.

### 7. Reranking

Scope:

- `RecommendationReranker`.
- OpenRouter rerank response parsing and candidate pruning.

Primary risks:

- Reranker chooses semantically weak candidates.
- Relevant candidates ranked below irrelevant ones.
- Malformed provider indices select wrong candidates.
- Top-n or candidate-limit settings over-prune true matches.
- Run-to-run instability.

Code-based checks:

| Check | Method |
| --- | --- |
| Index bounds | Reject `candidate_index < 0` and `>= len(candidates)` |
| Score presence | Every kept row has a reranker score |
| Candidate mapping | Returned index maps to the original limited candidate |
| Empty response fallback | Worker falls back intentionally and records the path |
| Config validation | `rerank_top_n` and `rerank_candidate_limit` are >= 1 |

Gold-label metrics:

| Metric | Meaning |
| --- | --- |
| Precision@k | Fraction of top k reranked candidates that are true links |
| MRR | First true link rank after rerank |
| NDCG@k | Ranking quality with graded relevance |
| Rerank lift | Difference versus semantic-only ranking |

LLM judge, only if human labels are sparse:

| Judge | Binary criterion |
| --- | --- |
| Pair is a true semantic match | Pass if the FMSI recommendation and UPR row express materially the same advocacy ask |

The pair-match judge must be validated against human labels before its scores
are used as regression gates.

### 8. End-to-End Match Quality

Scope:

- Full document pair -> final rendered recommendations.

Primary risks:

- Good stage metrics but poor final user value.
- Duplicate or redundant matches.
- Missing obvious matches.
- Incorrect supported/noted status from target row.
- Bad score calibration in UI.

Human-label metrics:

| Metric | Meaning |
| --- | --- |
| Final precision | Fraction of returned matches marked correct |
| Final recall | Fraction of expected gold links returned |
| F1 | Balance of precision and recall |
| False positive rate | Returned matches marked incorrect |
| Missing-match rate | Gold links absent from final output |
| Duplicate source rate | Multiple redundant rows for same source recommendation |

Code-based checks:

| Check | Method |
| --- | --- |
| Non-empty prediction | Expected smoke cases produce at least one match |
| Stable response shape | UI/API fields map correctly |
| Status derivation | `noted` vs `supported` comes from target row status |
| Download parity | XLSX export has same rows as UI table |

Review workflow:

- Render final matches in a reviewer-friendly table.
- Let domain reviewers mark each match correct/incorrect.
- Capture notes for missed or weak matches.
- Feed those labels back into `match_links.jsonl`.

### 9. Operational And Cost Evaluation

Scope:

- Latency, reliability, cost, and failure handling for live AI calls.

Metrics:

| Metric | Stage |
| --- | --- |
| Extraction latency | FMSI recommendation extraction |
| Embedding latency | UPR and FMSI embedding calls |
| Rerank latency | Rerank call per source recommendation |
| End-to-end job duration | Full worker job |
| Provider error rate | OpenRouter calls |
| Retry/fallback rate | Worker fallback paths |
| Token/request cost | OpenRouter extraction |
| Payload size | Uploaded files and worker-stage artifacts |

Gates:

- Live smoke must complete within a documented timeout.
- Provider failures should produce clear failed jobs or intentional fallbacks.
- No swallowed errors without trace artifacts.

## Evaluation Run Modes

| Mode | Trigger | Network | Purpose |
| --- | --- | --- | --- |
| Unit | Every PR | No | Deterministic parsers, schema checks, mocked OpenRouter clients |
| Local smoke | Before review | Optional | One document pair through API/worker |
| Browser E2E | Before release | Yes | Real file upload, progress polling, and rendered backend results |
| Nightly live eval | Scheduled | Yes | Regression metrics over curated cases |
| Model bakeoff | Manual | Yes | Compare extraction/embedding/rerank models |

Current CLI:

```sh
uv run --project backend python evals/tools/run_ai_pipeline_eval.py \
  --source-mode gold \
  --source-language es \
  --candidate-top-k 10 \
  --skip-reranker \
  --run-id costa_rica_full_es_gold
```

## Initial Milestones

### Milestone 1 - Trace Capture

- Define trace JSON schema.
- Add a live eval script that runs one document pair and writes all stage
  artifacts.
- Use Costa Rica 2024 as the first direct-label baseline case.
- Record model IDs, settings, timings, request sizes, and raw model responses.

### Milestone 2 - Deterministic Checks

- Add unit tests for backend DOCX row extraction using representative DOCX fixtures.
- Add unit tests for PDF extraction fixtures or extracted text snapshots.
- Add backend tests for multipart job payload validation.
- Add embedding shape/order tests with mocked or cached local embedder responses.
- Add rerank index-bounds and config-validation tests.

### Milestone 3 - Human Gold Set

- Review 30-50 traces.
- Build the first failure taxonomy from observed failures.
- Label FMSI recommendations, UPR rows, and match links for 5-10 document pairs.
- Store labels under `evals/gold/`.

### Milestone 4 - Metrics Report

- Compute extraction precision/recall against gold labels.
- Compute semantic retrieval Recall@k and threshold recall.
- Compute rerank Precision@k, MRR, and NDCG@k.
- Compute final match precision/recall/F1.
- Compare current run to the previous baseline.

### Milestone 5 - Validated Judges

- Pick one high-impact failure mode that code cannot check.
- Write one binary judge for that failure mode.
- Validate it against human labels with train/dev/test splits.
- Require at least 80% TPR and 80% TNR before using it internally.
- Target 90%+ TPR and 90%+ TNR before using it as a release gate.

## Candidate Failure Categories To Discover, Not Assume

These are hypotheses to look for during trace review, not pre-baked labels:

- FMSI extractor misses an implicit recommendation.
- FMSI extractor invents or paraphrases beyond the source text.
- FMSI extractor splits one recommendation into several fragments.
- FMSI extractor merges multiple recommendations into one.
- Theme or beneficiary classification is wrong.
- UPR table extraction drops rows under a theme section.
- Embedding retrieval misses semantically equivalent UPR rows.
- Cosine threshold filters out a true match.
- Reranker prefers a thematically related but substantively different row.
- Final output contains duplicates for the same source recommendation.
- UI score implies confidence that reviewers do not agree with.

## Release Gates, Once Baselines Exist

Do not enforce hard metric gates until the gold set is stable. Until then, use
the evals for diagnosis and trend tracking.

Suggested first gates after baselining:

| Gate | Initial target |
| --- | --- |
| Schema validity | 100% for extraction and prediction payloads |
| Backend extraction smoke | Pass on Costa Rica fixture |
| FMSI quote grounding | No regression versus baseline |
| Semantic Recall@30 | No regression versus baseline |
| Rerank Precision@5 | No regression versus baseline |
| Final match precision | No regression versus baseline |
| Final match recall | No regression versus baseline |
| Live job completion | Pass within timeout for smoke case |

## Open Questions

1. Which document pairs should be in the first curated eval set besides Vanuatu?
2. Who is the domain reviewer for initial labels?
3. Should gold match links be binary or graded relevance?
4. What is the acceptable tradeoff between recall and precision for the UI?
5. Which model IDs should be pinned for extraction, embeddings, rerank, and judges?
6. How much live OpenRouter spend is acceptable for nightly evals?
7. Which checks should run in the backend CLI, API/worker smoke, browser E2E, or all three?
