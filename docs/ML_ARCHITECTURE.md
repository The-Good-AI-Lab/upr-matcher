# ML Architecture — UPR Matcher

This document explains the machine-learning design behind UPR Matcher: **what** the
system does, **how** the pipeline is built, and **why** each decision was made.

> **The problem in one sentence:** given an NGO advocacy document (FMSI) and the
> official UN Universal Periodic Review (UPR) outcome document, automatically find
> which of the NGO's recommendations were picked up — referenced, accepted, or
> considered — by States during the review.

It is fundamentally a **semantic matching** problem between two sets of free-text
recommendations written by different authors, in different styles, that mean the
same thing. There is no shared ID to join on, so the system has to match on meaning.

---

## 1. The pipeline at a glance

The ML work is a four-stage pipeline, orchestrated in
[`worker.py`](../backend/fmsi_un_recommendations/_build_matches) (`_build_matches`):

```
  FMSI PDF ──► [1] Extract ──► [2] Embed ──► ┐
                                             ├─► [3] Match (bi-encoder, cosine) ──► [4] Rerank (cross-encoder) ──► matches
  UN DOCX  ──► [1] Extract ──► [2] Embed ──► ┘
```

| Stage | Input | Output | Technique | Code |
| --- | --- | --- | --- | --- |
| **1. Extract** | Raw PDF / DOCX | Structured recommendation records | LLM (FMSI) + deterministic table parse (UN) | `recommendation_processing.py`, `utils.py` |
| **2. Embed** | Recommendation text | Dense vectors (768-d) | Bi-encoder embeddings (`fastembed`) | `similarity_search.py` |
| **3. Match** | Two vector sets | Candidate pairs above a threshold | Cosine similarity, all-pairs | `similarity_search.py` |
| **4. Rerank** | Candidate pairs per FMSI rec | Pruned, re-scored matches | Cross-encoder + dynamic top-k | `reranker.py` |

Each stage is a clean input→output function, so stages can be developed, tested, and
swapped independently. The whole pipeline runs asynchronously in a worker subprocess
(see §6).

---

## 2. Stage 1 — Extraction (two different documents, two different strategies)

The two inputs have very different structure, so they get different extraction
strategies. **This is the key "why" of stage 1: use the cheapest reliable method per
document type.**

### UN document → deterministic table parsing

The UN UPR outcome document is a **DOCX with structured tables**. Tables have a fixed
schema (headers in row 1, data below), so an LLM would be overkill and would risk
hallucinating. Instead, `docx_tables_to_json` ([`utils.py`](../backend/fmsi_un_recommendations/utils.py))
walks the tables deterministically:

- The first row is treated as the header; subsequent rows become `{header: cell}` dicts.
- Single-cell rows starting with `Theme:` are recognized as section titles and folded
  into following rows as `current_theme` metadata (so each recommendation carries its theme).
- Rows whose cell count doesn't match the header, or that are entirely empty, are skipped.

**Why deterministic:** the data is already structured, parsing is free and 100%
reproducible, and there is no risk of an LLM inventing content. Verifiable by
construction — the output is a faithful transcription of the table.

### FMSI document → LLM extraction

The FMSI document is a **free-form advocacy PDF**. Recommendations are written in prose
and bullet points with no fixed schema, usually grouped near the end. This is exactly
where deterministic parsing breaks down and an LLM shines.

`extract_fmsi_pdf_recommendations` ([`recommendation_processing.py`](../backend/fmsi_un_recommendations/recommendation_processing.py)):

1. Extracts raw text from the PDF (`pypdf`).
2. **Chunks** the text into ≤80 000-char pieces on paragraph boundaries (`_chunk_text`)
   so large documents fit within the model context window.
3. For each chunk, calls the LLM with a fixed system prompt
   ([`prompts/recommendation_extraction.txt`](../backend/prompts/recommendation_extraction.txt))
   that instructs it to extract **exact-citation** recommendations and classify each into a
   `recommendation / domain / beneficiaries / theme` schema, choosing `theme` from a fixed
   controlled vocabulary.
4. Parses the JSON response and **validates** it against the `Recommendation` Pydantic model.
5. **Deduplicates** by normalized lowercase text (`_dedupe_recommendations`), since chunk
   overlap and repetition can surface the same recommendation twice.

**Why an LLM here:** unstructured prose with implicit recommendations is a natural-language
understanding task. The prompt explicitly says *"Only use information directly from the
provided documents. Do not generate or infer content"* and asks for **direct citations** —
a deliberate guardrail to keep extraction grounded and auditable rather than generative.

**Why a controlled theme vocabulary:** forcing the LLM to choose from a fixed list (rather
than free-text themes) keeps the downstream category summaries consistent and comparable
across runs.

> **Note / known wrinkle:** there is also a pure-regex extractor
> `extract_fmsi_recommendations_algo` that parses letter-bullets (`a.`, `b.` …) and a
> conclusion section. It exists as a cheaper, LLM-free fallback/experiment, but the worker
> pipeline currently uses the LLM path. The `RecommendationBatch` validation line in
> `extract_fmsi_pdf_recommendations` builds a plain list rather than the wrapper model — a
> minor inconsistency worth tidying.

---

## 3. Stage 2 — Embeddings (bi-encoder)

Both recommendation sets are turned into dense vectors with a **bi-encoder** sentence
embedding model via [`fastembed`](https://github.com/qdrant/fastembed):

- **Model:** `BAAI/bge-base-en-v1.5` (768-dimensional, English), configurable in
  [`settings.py`](../backend/fmsi_un_recommendations/settings.py).
- UN rows are embedded from a **flattened `key: value` text payload** of the whole row
  (`_row_to_text_payload`) — theme, domain, recommendation text, etc. — so all available
  structured context contributes to the vector.
- FMSI recommendations are embedded from the **recommendation text only**.
- The embedder is a lazily-initialized singleton (`get_text_embedder`) so the model is
  loaded once per process.

**Why a bi-encoder:** bi-encoders embed each text independently, so the two document sets
can be encoded **once** and then compared with cheap vector math. This makes the all-pairs
comparison in stage 3 affordable. (A cross-encoder, by contrast, must re-run the model on
every pair — too expensive as the first pass.)

**Why `fastembed` / BGE:** `fastembed` runs the model locally via ONNX (no API calls, no
per-token cost, runs on CPU), and `bge-base-en-v1.5` is a strong, widely-used retrieval
embedding model with a good quality/size trade-off. Keeping embeddings local also keeps
sensitive document content off third-party embedding APIs.

---

## 4. Stage 3 — Candidate matching (cosine similarity, all-pairs)

`match_recommendation_vectors` ([`similarity_search.py`](../backend/fmsi_un_recommendations/similarity_search.py))
computes **cosine similarity for every (FMSI, UN) pair** and keeps those at or above a
threshold.

- Cosine similarity is implemented by hand (`cosine_similarity`) — dot product over the
  product of norms.
- The threshold is configurable; the worker uses `settings.match_threshold` (**default
  0.6**). The function's own default arg is `0.7`, but the worker passes the settings value.
- Results are sorted by score descending and carry both rows' non-embedding fields plus the
  text payloads, ready for reranking and storage.

**Why all-pairs (no ANN index):** the document sets are small (tens to low hundreds of
recommendations each), so an exhaustive O(n·m) comparison is trivially fast and avoids the
complexity of a vector database / approximate-nearest-neighbour index. The design favours
**simplicity and exactness over scale** — appropriate for the actual data size.

**Why a recall-oriented threshold:** this stage is intentionally a **high-recall first
pass**. A relatively low cosine threshold (0.6) lets through generous candidates rather
than prematurely discarding true matches; precision is recovered in the rerank stage. This
is the classic **retrieve-then-rerank** pattern.

---

## 5. Stage 4 — Reranking (cross-encoder + dynamic top-k)

For each FMSI recommendation, its surviving UN candidates are re-scored by a **cross-encoder**
([`reranker.py`](../backend/fmsi_un_recommendations/reranker.py)):

- **Model:** `cross-encoder/ms-marco-MiniLM-L6-v2` (a `sentence-transformers` CrossEncoder),
  run on MPS / CUDA / CPU automatically (`_default_device`), in `torch.inference_mode()`.
- For a given FMSI query, the model scores every `[query, candidate]` pair **jointly** and
  sorts candidates by score.
- A **dynamic top-k** (`dynamic_k_by_drop`) decides how many to keep: walk down the sorted
  scores and cut at the first **relative drop** ≥ 20 % once at least `min_k` are kept,
  bounded by `[min_k=1, max_k=10]`.

**Why a cross-encoder second pass:** cross-encoders read the query and candidate *together*,
so they capture fine-grained semantic alignment that independent bi-encoder vectors miss.
They are far more accurate but too slow to run on all pairs — so they are applied only to the
small candidate set the bi-encoder already shortlisted. Retrieve cheaply, rerank precisely.

**Why dynamic-k instead of a fixed cutoff:** the right number of true matches varies per
recommendation — some FMSI recommendations map to one UN item, others to several. A fixed
top-k would either truncate real matches or pad with weak ones. Cutting at the first sharp
**score drop-off** adapts the count to where the model itself signals the quality cliff.

**Why it's wrapped in try/except:** in the worker, reranking is best-effort. If the
cross-encoder fails to load or errors, the pipeline **falls back to the bi-encoder matches**
rather than failing the whole job (`worker.py`, "Reranking failed … using semantic
similarity matches only"). Graceful degradation over hard failure.

---

## 6. Serving architecture & operational decisions

The ML pipeline is long-running (model loading + inference), so it is decoupled from the API:

- **Async job queue.** `POST /matches` only persists the uploads and **enqueues a job**, then
  returns a `job_id` immediately ([`api.py`](../backend/fmsi_un_recommendations/api.py)). The
  frontend polls `GET /progress/{job_id}` for percent/stage updates written by the pipeline's
  `report(...)` callbacks. This keeps the request fast and the UI responsive on slow jobs.
- **One subprocess per job.** The worker (`run_worker`) polls for pending jobs and runs each in
  its **own `multiprocessing.Process`**. The deliberate reason (documented in `_execute_job`):
  ML model memory — fastembed ONNX buffers, cross-encoder weights, torch tensors — is fully
  **released when the subprocess exits**, even after a SIGKILL from an OOM killer. This prevents
  memory accumulation across back-to-back jobs and isolates a crash to a single job; the parent
  loop survives and picks up the next one. OOM exits are detected via `proc.exitcode` and the job
  is marked failed with a user-friendly message.
- **Resilience.** Stale jobs (no progress > 1h) are auto-failed; orphaned jobs are recovered on
  startup; the poll loop uses exponential backoff on repeated DB errors.
- **Persistence.** Each run stores inputs, the normalized UN/FMSI rows (optionally **with
  embeddings**, `store_embeddings`), and the match payloads, so predictions are reproducible and
  re-viewable without recomputation. SQLite locally, PostgreSQL in deployment, behind one adapter.
- **Human feedback loop.** `POST /feedback` records a thumbs-up/down per match. This captures
  ground-truth labels on real predictions — the raw material for future evaluation or model
  improvement, even though no automated retraining exists yet.

---

## 7. Model & configuration summary

All ML knobs live in [`settings.py`](../backend/fmsi_un_recommendations/settings.py) (env-overridable):

| Setting | Default | Role |
| --- | --- | --- |
| `model` | `meta-llama/llama-3.3-70b-instruct` (via OpenRouter) | LLM for FMSI extraction |
| `embedding_model` | `BAAI/bge-base-en-v1.5` | Bi-encoder embeddings (stage 2) |
| `match_threshold` | `0.6` | Cosine cutoff for candidate matches (stage 3) |
| cross-encoder | `cross-encoder/ms-marco-MiniLM-L6-v2` | Rerank model (stage 4) |
| `reranker_batch_size` | `16` | Cross-encoder batch size |
| rerank `min_k` / `max_k` | `1` / `10` | Bounds on matches kept per FMSI rec |
| `rel_drop_threshold` | `0.20` | Score-drop cutoff for dynamic-k |
| `store_embeddings` | `true` | Persist embeddings with predictions |

**Why OpenRouter + an open model:** OpenRouter gives a single OpenAI-compatible API across many
models, so the LLM can be swapped via config without code changes. A capable open model
(Llama 3.3 70B) handles structured extraction well at lower cost than frontier proprietary models.

---

## 8. Design philosophy (the "why" in one place)

1. **Right tool per sub-problem.** Deterministic parsing for structured tables; an LLM only where
   language understanding is genuinely needed. Don't pay for an LLM where a parser suffices.
2. **Retrieve cheaply, rerank precisely.** A fast bi-encoder produces high-recall candidates; an
   accurate-but-slow cross-encoder refines a small shortlist. Classic two-stage retrieval.
3. **Adapt to the data, don't hard-code.** Dynamic top-k lets each recommendation keep as many
   matches as the scores justify, instead of a one-size-fits-all cutoff.
4. **Grounded, auditable extraction.** Exact-citation prompting and a controlled theme vocabulary
   keep outputs traceable to the source and consistent across runs.
5. **Degrade gracefully, isolate failure.** Reranking falls back to bi-encoder matches; each job
   runs in a disposable subprocess so OOM/crashes never take down the service.
6. **Simplicity over premature scale.** All-pairs comparison and local embeddings fit the actual
   (small) data size — no vector DB, no external embedding API, fully reproducible.
7. **Capture human judgment.** The feedback endpoint banks labels on real predictions for future
evaluation and improvement.
```
