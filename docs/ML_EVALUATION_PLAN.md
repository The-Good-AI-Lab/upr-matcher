# ML Evaluation Plan - UPR Matcher

This is the focused plan for evaluating the ML behavior of UPR Matcher. It
intentionally excludes UI checks, API contract checks, and deterministic parser
robustness except where those checks protect the validity of ML metrics.

Current PR-level results are summarized in `evals/RESULTS.md`. Generated traces,
reports, and labeling queues are local artifacts under ignored `evals/traces/`,
`evals/reports/`, and `evals/labeling/` directories.

The ML system under evaluation is:

```text
source document text
  -> LLM source recommendation extraction
  -> source and UPR row embeddings
  -> semantic candidate retrieval
  -> reranking
  -> final source-to-UPR match set
```

## Current Evidence

Direct match labels currently exist for `costa_rica_2024`.

Latest labeled gold-source regression runs:

| Run | Language pair | hit@10 | recall@10 | MRR | NDCG@10 |
| --- | --- | ---: | ---: | ---: | ---: |
| `costa_rica_parser_regression_es_gold` | `es-en` | 0.7778 | 0.3722 | 0.3455 | 0.3046 |
| `costa_rica_parser_regression_en_gold` | `en-en` | 0.9444 | 0.6482 | 0.6972 | 0.5783 |

Interpretation:

- The same-language `en-en` control is much stronger than the real `es-en`
  condition, so cross-lingual retrieval is a primary ML risk.
- The parser fix improved Costa Rica target ID coverage to 1.0, but retrieval
  metrics did not move. That means the next bottleneck is ML ranking quality,
  not row extraction.
- OpenRouter source extraction is still nondeterministic. One live smoke
  extracted 28 recommendations with full gold coverage; an earlier run grouped
  bullets and extracted only 7 recommendations. This stage needs repeated-run
  evaluation, not one-off smoke tests.

Unlabeled UPR materials are useful for robustness and sampling, but they are not
ML accuracy evidence until we add human match labels.

## Evaluation Principles

1. Evaluate stages separately before judging the final result.
2. Use retrieval metrics for retrieval and reranking: Recall@k, MRR, NDCG@k,
   Precision@k, and rerank lift.
3. Use code checks only for objective facts: schema validity, empty output,
   duplicate IDs, count preservation, malformed provider responses.
4. Use LLM judges only for semantic criteria that cannot be checked with code.
5. Validate every judge against human labels with TPR and TNR before trusting
   it.
6. Report `es-en` and `en-en` separately before aggregating.
7. Keep traces for every live model run so drift and prompt changes are visible.

## Stage Metrics

### 1. Source Recommendation Extraction

Question: does the LLM extract the true FMSI advocacy recommendations from the
source document?

Required labels:

- Canonical source recommendation ID.
- Recommendation text.
- Source span or evidence snippet.
- Optional theme and beneficiary labels.

Code checks:

- JSON/schema validity.
- Non-empty recommendation/domain/beneficiaries/theme.
- Duplicate normalized recommendation rate.
- Count of extracted recommendations.
- Fuzzy source-span grounding candidate.

Human-label metrics:

| Metric | Meaning |
| --- | --- |
| Extraction recall | Fraction of human source recommendations recovered |
| Extraction precision | Fraction of extracted recommendations that are real recommendations |
| Count error | Absolute difference between extracted and human counts |
| Duplicate rate | Fraction of repeated or near-duplicate extracted recommendations |
| Grounding pass rate | Fraction supported by the source document |

Protocol:

- Run each live extraction case 3-5 times.
- Record mean, min, max, and worst trace.
- Treat the minimum run quality as the release-risk signal, not only the mean.

### 2. Semantic Candidate Retrieval

Question: does embedding search put relevant UPR rows into the candidate set?

Primary metric:

- Recall@k, especially Recall@10 and Recall@30.

Supporting metrics:

- hit@k.
- MRR.
- NDCG@k for graded labels (`very_similar` > `similar`).
- Average candidates per source after thresholding.
- Threshold recall.

Decision rule:

- This stage should optimize recall. A true match filtered out here cannot be
  recovered by the reranker.

Current baseline:

| Condition | Recall@10 | Key risk |
| --- | ---: | --- |
| `es-en` | 0.3722 | Cross-lingual source-to-target retrieval |
| `en-en` | 0.6482 | General semantic retrieval ceiling |

### 3. Reranking

Question: given a candidate set containing true matches, does the reranker move
the best candidates upward without dropping relevant rows?

Metrics:

| Metric | Meaning |
| --- | --- |
| Precision@k | Fraction of top k reranked candidates that are true links |
| MRR | Rank of the first true link after rerank |
| NDCG@k | Ranking quality with graded relevance |
| Rerank lift | Difference versus semantic-only ranking |
| Recall retention | Fraction of semantic candidates still reachable after reranking |

Current status:

- The small English reranker smoke hurt metrics. Do not use reranking as a
  release gate until we have more labeled candidate pairs and a real rerank
  sweep.

### 4. Final Match Quality

Question: are the returned matches useful and correct for a reviewer?

Metrics:

- Final precision.
- Final recall.
- F1.
- False positive rate.
- Missing-match rate.
- Duplicate source recommendation rate.

This requires human labels over final outputs, not only candidate-level labels.

### 5. LLM Semantic Judges

Do not build broad "match quality" judges first. Build one binary judge per
observed failure mode after error analysis.

Candidate judges, after labels exist:

| Judge | Binary criterion |
| --- | --- |
| Pair is a true semantic match | Source recommendation and UPR row express materially the same ask |
| Source extraction is grounded | Extracted recommendation is supported by source text |
| Source extraction is complete | Extracted recommendation contains the full ask, not a fragment |

Validation requirement:

- Use train/dev/test splits.
- Few-shot examples come only from train.
- Tune on dev.
- Report final TPR and TNR once on test.
- Minimum internal target: TPR >= 0.80 and TNR >= 0.80.
- Release-gate target: TPR >= 0.90 and TNR >= 0.90.

## Labeling Plan

### Immediate Gold Set

Use Costa Rica as the first direct-label dataset.

Add negative and candidate-level labels:

1. For each labeled Costa Rica source recommendation, export top semantic
   candidates from both `es-en` and `en-en` runs.
2. Keep one row per `(source_id, target_id, language_pair)` so we can compare
   Spanish and English retrieval directly.
3. Human-label each pair as:
   - `very_similar`
   - `similar`
   - `not_relevant`
   - `unclear`
4. Add `failure_category` for `not_relevant` rows:
   - `theme_only`
   - `too_broad`
   - `too_narrow`
   - `cross_lingual_miss`
   - `general_retrieval_miss`
   - `label_ambiguous`
   - `other`
5. Keep `unclear` out of automated metrics until adjudicated.

This gives us a real precision signal, not only recall against positive links.

### Next Direct-Label Cases

Bangladesh and Papua New Guinea have weaker advocacy-impact labels. Treat them
as coarse checks until we verify their workbooks encode direct source-to-UPR
similarity. Do not mix them into Costa Rica precision/recall metrics unless the
label semantics match.

For the larger UPR materials folder:

- Sample a small, diverse set across language and country.
- Manually label source recommendations and UPR matches.
- Prioritize cases with Spanish or non-English source documents because
  language is already the biggest observed gap.

Target:

- Short term: 3-5 direct-label document pairs.
- Medium term: 20-30 direct-label document pairs or 100 reviewed traces.

## Error Analysis Workflow

Before adding more judges or model changes, review traces and label the first
failure point.

Suggested failure categories to discover, not assume:

| Category | First thing that went wrong |
| --- | --- |
| Source extraction miss | True FMSI recommendation was not extracted |
| Source extraction over-split | One recommendation became multiple fragments |
| Source extraction under-split | Multiple recommendations were grouped together |
| Cross-lingual retrieval miss | `en-en` succeeds but `es-en` misses |
| General retrieval miss | Both `es-en` and `en-en` miss |
| Theme-only false positive | Candidate shares topic but not the same ask |
| Over-broad recommendation | Candidate is related but materially broader/narrower |
| Reranker demotion | True candidate existed but reranker moved it down |
| Label ambiguity | Human label is unclear or inconsistent |

Review protocol:

1. Start with Costa Rica traces.
2. Inspect top 10 candidates per source for `es-en` and `en-en`.
3. Mark pass/fail at the source recommendation level.
4. Record the first failure category.
5. Use the category counts to choose the next fix or evaluator.

## Regression Gates

Until we have more direct-label cases, use gates as warning signals, not hard
product-quality claims.

Current PR gate:

- Costa Rica `es-en` semantic metrics must not regress from:
  - hit@10: 0.7778
  - recall@10: 0.3722
  - MRR: 0.3455
- Costa Rica `en-en` semantic metrics must not regress from:
  - hit@10: 0.9444
  - recall@10: 0.6482
  - MRR: 0.6972
- Source extraction live smoke must record trace artifacts and cost.

Model bakeoff gate:

- Compare models on the same trace inputs.
- Report `es-en` and `en-en` separately.
- Prefer improvements that reduce the `es-en` gap without hurting `en-en`.
- Require repeated extraction runs for LLM extraction comparisons.

## Implemented Candidate Labeling Queue

The current ML eval code lives at:

- `evals/tools/run_ml_eval_suite.py`
- `evals/tools/compare_embedding_models.py`
- `evals/tools/evaluate_extraction_stability.py`
- `evals/tools/evaluate_reranker_lift.py`
- `evals/tools/evaluate_final_match_quality.py`
- `evals/tools/validate_binary_judge_labels.py`
- `evals/tools/build_candidate_labeling_queue.py`
- `evals/tools/summarize_candidate_labels.py`

Run the default offline suite with:

```sh
uv run --project backend python evals/tools/run_ml_eval_suite.py
```

This refreshes deterministic labeling artifacts, summarizes human-label
coverage, reports retrieval baselines from existing traces, and computes
reranker lift from traces that contain reranker outputs.

Opt-in stage runs:

```sh
# Recompute local retrieval baselines.
uv run --project backend python evals/tools/run_ml_eval_suite.py \
  --refresh-baselines \
  --allow-openrouter-embeddings

# Run local reranker sweeps, then summarize lift.
uv run --project backend python evals/tools/run_ml_eval_suite.py \
  --run-reranker-sweep \
  --allow-openrouter-embeddings \
  --allow-openrouter-reranker

# Compare OpenRouter embedding models. Use dry-run first to avoid accidental
# paid calls.
uv run --project backend python evals/tools/run_ml_eval_suite.py \
  --embedding-model-sweep qwen/qwen3-embedding-8b \
  --embedding-model-sweep openai/text-embedding-3-small \
  --embedding-provider openrouter \
  --dry-run-embedding-sweep

uv run --project backend python evals/tools/run_ml_eval_suite.py \
  --embedding-model-sweep qwen/qwen3-embedding-8b \
  --embedding-model-sweep openai/text-embedding-3-small \
  --embedding-provider openrouter \
  --allow-openrouter-embeddings

# Run repeated live extraction with OpenRouter budget.
uv run --project backend python evals/tools/run_ml_eval_suite.py \
  --run-extraction-repeats \
  --allow-openrouter \
  --extraction-repeats 3 \
  --max-cost-usd 10
```

The first candidate labeling queue generator uses generated baseline traces.
These paths are examples of local outputs, not committed fixtures:

Input:

- `evals/traces/live/costa_rica_parser_regression_es_gold.json`
- `evals/traces/live/costa_rica_parser_regression_en_gold.json`

Generated output:

- `evals/labeling/costa_rica_candidate_pairs.jsonl`
- Current generated size: 540 blinded review rows with blank human label fields.
- `evals/labeling/costa_rica_candidate_pairs_with_gold.jsonl`
- Current generated size: 540 enriched analysis rows, with 69 known positive
  gold labels attached.
- `evals/labeling/costa_rica_missing_gold_pairs.jsonl`
- Current generated size: 111 rows, covering known gold positives absent from
  top-10 candidates.
- `evals/reports/costa_rica_candidate_label_metrics.md`

Initial generated reports show label coverage only; precision metrics become
meaningful after `human_relevance` is filled.

Each row should include:

- `case_id`
- `source_id`
- `source_language`
- `source_text`
- `target_id`
- `target_text`
- `rank`
- `semantic_score`
- blank human label fields: `human_relevance`, `failure_category`,
  `review_notes`

The candidate queue is the bridge from our current positive-only labels to
candidate precision, false-positive analysis, language effects, and future
judge alignment. The blinded queue should be used for human review; the
`*_with_gold` file is for analysis after labels are collected. The missed-gold
file keeps recall failures explicit instead of hiding them outside the top-10
candidate review queue.

Next human action:

- Review the 540 blinded candidate rows.
- Fill `human_relevance` with `very_similar`, `similar`, `not_relevant`, or
  `unclear`.
- Fill `failure_category` for `not_relevant` rows.
- Use `review_notes` for extra context that does not fit the category.
- Compare against the enriched `*_with_gold` file only after human labels are
  collected.
- Review the 111 missed-gold rows to categorize why known positives fell outside
  top-10; these rows are already known positives, so the main label is the
  failure category.

After labels are filled, run:

```sh
uv run --project backend python evals/tools/summarize_candidate_labels.py
```

This reports candidate precision by language pair and rank, plus failure
category counts for candidate false positives and missed-gold false negatives.
