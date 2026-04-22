# UPR-Matcher

## Project Description

This project analyzes UN Universal Periodic Review (UPR) recommendations submitted by FMSI and other NGOs, focusing on how these recommendations are referenced, accepted, or considered by States under review. It aims to:

### Objectives

- Analyze which recommendations submitted by FMSI and other NGOs have been referenced by other States and presented to the State under review.
- Identify which of these recommendations have been accepted or considered by the State under review.

## Architecture

The app is split into three services:

- **Backend** (`backend/`) - FastAPI service for uploads, matching, and persistence APIs.
- **Worker** (`backend/`) - Background process for long-running recommendation processing.
- **Frontend** (`frontend/`) - React/TypeScript UI for uploads, progress, results, and feedback.

## Quick start (local, full stack)

```sh
docker compose up --build
```

- Frontend: `http://localhost:80`
- Backend API: `http://localhost:8000`

The worker runs alongside the backend in Docker Compose.

### Backend only (no Docker)

```sh
cd backend && uv sync --all-extras && uv run app
```

In a separate terminal:

```sh
cd backend && uv run worker
```

See [backend/README.md](backend/README.md) for backend setup, environment variables, and endpoints.

## Docker images

Backend (and later frontend) images are built in CI and pushed to **GitHub Container Registry** (`ghcr.io`). Tags follow branch/commit/release:

- **Branch** (e.g. `feature/foo`): `branch-name`, `branch-name-<7char-sha>`
- **main**: `main`, `main-<7char-sha>`, `latest`
- **Release tag** (e.g. `v1.0.0`): the tag as-is

**Run the backend image locally:**

```sh
docker run --rm -p 8000:8000 -e OPENROUTER_API_KEY=your-key ghcr.io/<owner>/<repo>/backend:latest
```

**Deployment** - The app is deployed with the [k8s-apps](https://github.com/The-Good-AI-Lab/k8s-apps) repo via Helm (`apps/upr-matcher/`). Use the image tags above in Helm values to pin to a branch, commit, or release.

## Prek (lint & format)

The project uses [prek](https://prek.j178.dev/) for pre-commit hooks (same `.pre-commit-config.yaml`).

**Install** (one of):

```sh
curl --proto '=https' --tlsv1.2 -LsSf https://github.com/j178/prek/releases/download/v0.3.1/prek-installer.sh | sh
# or: uv tool install prek
# or: brew install prek
```

From repo root: `prek install` then `prek run` from anywhere in the repo (or `prek run --all-files`). CI runs the same checks via the Backend workflow (`.github/workflows/backend.yaml`, which calls `common.yaml`).

## Repository layout

| Path | Description |
| --- | --- |
| `backend/` | FastAPI app, worker logic, scripts, prompts, tests |
| `frontend/` | React/TypeScript UI |
| `.github/workflows/` | CI for backend/frontend image builds |
| `docker-compose.yaml` | Local backend + worker + frontend stack |
