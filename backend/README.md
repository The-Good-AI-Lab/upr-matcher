# Backend

## Installation & Development

This project uses [uv](https://github.com/astral-sh/uv), a fast Python package manager and workflow tool. To get started:

### 1. Install uv

You can install uv by following the instructions at the [uv GitHub page](https://github.com/astral-sh/uv) or run:

```sh
curl -Ls https://astral.sh/uv/install.sh | sh
```

Or, if you have Homebrew:

```sh
brew install uv
```

### 2. Install Project Dependencies

From **repo root**: `cd backend && uv sync --all-extras`.
From **this directory** (backend): `uv sync --all-extras`.

Dependencies are defined in this directory’s `pyproject.toml`. Lint and format (Prek) are configured at repo root; see the [root README](../README.md#prek-lint--format).

### 3. Development Workflow

- Use `uv` from this directory for dependencies and running the API.
- Run experiments in `notebooks/` (in this directory) with Jupyter.
- SQLite DB uses `data/` under this directory. Optional text payload snapshots use `data/uploads/`.

For more details on uv usage, see the [uv documentation](https://github.com/astral-sh/uv).

## API Service

The backend is a FastAPI app that runs the UN/FMSI matching workflow and persists each run. From **this directory**:

```sh
uv run app
```

From repo root: `cd backend && uv run app`. With auto-reload: `uvicorn fmsi_un_recommendations.api:create_app --reload`.

### Endpoints

- `POST /matches` – accepts JSON text fields: `fmsi_markdown`, `upr_rows`, and optional source/reference filenames. The frontend is responsible for converting the PDF/DOCX to text/table rows before calling this endpoint. The backend enqueues a worker job from those text fields.
- `POST /feedback` – accepts `prediction_id`, `match_id`, `thumb_up`, and optional `notes`. Verifies the match belongs to the stored prediction and records a thumbs-up/down.
- `GET /health` – simple readiness probe.

Text inputs are stored on the queued job so processing does not require saved input files. Set `SAVE_TEXT_PAYLOADS=true` to also write debugging snapshots under `data/uploads/`.

### Storage Backends

The API supports SQLite (local) and PostgreSQL (deployment) via a small adapter. Configure with the env vars below (see `fmsi_un_recommendations/settings.py`). Put a `.env` in this directory or export them.

- `DB_BACKEND`: either `local` (default) or `postgres`.
- `LOCAL_DB_PATH`: optional override for the SQLite path (default: `data/recommendations.db` under this directory).
- `DATABASE_URL`: required only when `DB_BACKEND=postgres`, e.g. `postgresql://user:pass@host:5432/dbname`.
- `SAVE_TEXT_PAYLOADS`: when `true`, also save submitted Markdown/UPR rows under `data/uploads/`; default is `false`.

The `jobs` table stores queued text payloads. The `predictions` table stores optional input snapshot paths, normalized UN/FMSI rows, and match payloads (each with a `match_id`). The `feedback` table stores thumbs-up/down keyed by `prediction_id` and `match_id`.

## Repository layout (this directory)

- **`fmsi_un_recommendations/`** – FastAPI app and DB adapter.
- **`data/`** – local SQLite DB and optional text payload snapshots.
- **`prompts/`** – LLM prompts.
- **`notebooks/`** – Jupyter experiments.
- **`scripts/`** – standalone scripts (embed, extract, match, etc.).
- **`tests/`** – tests for the API and processing.

## TODO

- Revisit licensing before any public release (GPLv3 may not be ideal for downstream consumers).
- Add API-level tests (FastAPI `TestClient`) covering the `/matches` and `/feedback` flows.
- Implement authentication/authorization for the FastAPI endpoints once deployment requirements are defined.
