# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Growth Chat is an AI engineering learning project structured as a monorepo with four modules:

- `documentation/` — DocMD static site (implemented)
- `backend/` — FastAPI backend with SSE streaming and domain-driven structure (scaffolded)
- `frontend/` — React + TypeScript + Vite chat widget (scaffolded)
- `data/database/` — SQL migration runner (implemented)
- `data/ingestion/` — knowledge ingestion pipeline (implemented, dev mode)
- `data/knowledge-base/` — source Markdown documents for ingestion (15 docs: services, team, case studies, engagement, FAQ)
- `evaluation/`, `shared/` — Python uv workspace members (stubs)

Node version: v24.15.0 (see `.nvmrc`; use `nvm use` before working in `documentation/`).

Python version: 3.14+ (see `.python-version`; managed via uv workspace).

## Documentation Module

All commands run from `documentation/`:

```bash
npm start        # dev server with live reload
npx docmd build  # build static site to site/
```

DocMD config lives in `docmd.config.js`. Content is Markdown in `docs/`. The generated `site/` directory is git-ignored.

## Backend Module

Managed as a uv workspace member. All commands run from the project root:

```bash
uv sync                                                                   # install all workspace deps
uv run --package backend uvicorn backend.main:app --reload --port 8000   # dev server
```

Source lives in `backend/src/backend/`. Domain structure:

- `conversation/` — `POST /chat` SSE route, request/response models, `SessionState`
- `qualification/` — `LeadLevel`, `FitLevel`, `QualificationState`
- `knowledge/` — `retrieve_knowledge()` stub (RAG interface)
- `handoff/` — `dispatch_handoff()` stub, `is_business_hours()`, `CRMClient` protocol
- `analytics/` — `emit_event()` stub

`backend/.env.example` lists all required environment variables. Copy to `backend/.env` before running.

## Database Module

Managed as a uv workspace member (`data/database`). All commands run from the project root:

```bash
uv run --package database python -m database.migrate            # apply pending migrations
uv run --package database python -m database.migrate --dry-run  # preview without applying
uv run --package database python -m database.migrate --rollback N  # roll back last N
```

Migrations are plain SQL files in `data/database/migrations/`, numbered `0001`–`0006`. Each has a matching `.down.sql` rollback file. The runner tracks applied versions in a `schema_migrations` table it creates on first run.

**Local development** uses Docker Compose (pgvector/pgvector:pg17). Start it with:

```bash
docker compose up -d
```

Copy `data/database/.env.example` to `data/database/.env` and set `CHECKPOINT_DB_URL` to the local Postgres URL before running migrations locally.

**Production** database is Neon PostgreSQL. The connection string is set via `CHECKPOINT_DB_URL` in the backend's environment and in the `production` GitHub environment secret.

Schema summary:

- `knowledge_chunks` — production vector store (1536-dim, OpenAI embeddings); columns: `chunk_id`, `source`, `chunk_index`, `content`, `content_hash`, `embedding`, `category`, `title`, `description`, `proactive_eligible`
- `knowledge_chunks_dev` — dev vector store (384-dim, HuggingFace embeddings); same columns as above
- `handoff_records` — human handoff audit trail
- `leads` — CRM substitute (structured lead records)
- `checkpoints` / `checkpoint_writes` — created at backend startup by LangGraph's `AsyncPostgresSaver`

## Ingestion Module

Managed as a uv workspace member (`data/ingestion`). All commands run from the project root:

```bash
uv run --package ingestion python -m ingestion.pipeline --source data/knowledge-base
```

Source lives in `data/ingestion/src/ingestion/`:

- `chunker.py` — `RecursiveCharacterTextSplitter`, deterministic SHA-256 `chunk_id`
- `embedder.py` — dev mode: `HuggingFaceEmbeddings` (`all-MiniLM-L6-v2`, 384-dim, no API key; ~90 MB downloaded to `~/.cache/huggingface/` on first run)
- `pipeline.py` — walks source dir, strips YAML frontmatter, chunks, embeds, upserts to `knowledge_chunks_dev`

Environment variables (copy `data/ingestion/.env.example` to `data/ingestion/.env`; loaded automatically at startup):

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `CHECKPOINT_DB_URL` | Yes | — | psycopg3 connection string |
| `CHUNK_SIZE` | No | `512` | Tokens per chunk |
| `CHUNK_OVERLAP` | No | `64` | Token overlap between adjacent chunks |

Source documents live in `data/knowledge-base/` as Markdown files with YAML frontmatter (`source`, `category`, `title`, `description`, `proactive_eligible`). 15 synthetic documents covering services, team, case studies, engagement models, and FAQ.

## Frontend Module

All commands run from `frontend/`:

```bash
npm run dev    # dev server with HMR at localhost:5173
npm run build  # type-check + IIFE bundle to dist/chat.js
```

The widget is a `<growth-chat>` Custom Element (Web Component) that mounts React inside a Shadow DOM. `src/GrowthChat.ts` is the wrapper; `src/components/ChatWidget.tsx` is the React component. `vite build` produces a single self-contained `dist/chat.js` IIFE for CDN distribution.

## Architecture Notes

- The uv workspace root is `pyproject.toml`. Members: `backend`, `data/database`, `data/ingestion`, `evaluation`, `shared/knowledge_base`.
- Code is organised by business domain, not technical layer (conversation, qualification, knowledge, handoff, analytics).
- Each module is independent; there is no root-level build system.
- The `backend/` package uses src layout (`src/backend/`). Import as `from backend.x import y`.

## CI/CD and Deployment

Three workflows in `.github/workflows/`: `deploy-backend.yml`, `deploy-frontend.yml`, `deploy-documentation.yml`. All trigger on push to `main` and support `workflow_dispatch` for manual runs.

Required secrets — must be set in the `production` GitHub environment:

- `FLY_API_TOKEN` — authenticates Docker push and Fly.io deploy (backend)
- `CHECKPOINT_DB_URL` — Neon PostgreSQL connection string; used by the migration job in `deploy-backend.yml`
- `TIGRIS_ACCESS_KEY_ID` / `TIGRIS_SECRET_ACCESS_KEY` — S3-compatible credentials for Fly Tigris object storage (frontend)

**Backend:** The deploy workflow runs two sequential jobs: `migrate` (applies pending SQL migrations to Neon via the `database` package) then `build-and-deploy` (builds and pushes the Docker image to Fly.io). A migration failure blocks the deploy. Production runs on port **8080** (dev uses 8000). Fly.io config is `backend/fly.toml` (Frankfurt region, auto-scale to 0, `shared-cpu-1x`, 256 MB). Docker build context must be the **project root** so the uv workspace is available:

```bash
docker build -f backend/Dockerfile -t growth-chat-api .
```

**Frontend:** Build artifact is `dist/chat.js` (single IIFE). The CI workflow uploads it to Fly Tigris object storage with a 1-hour cache TTL. CDN bucket name and endpoint URL live in the workflow env vars — not in source. Required build-time env vars (`VITE_API_URL`, `VITE_FALLBACK_URL`, `VITE_GDPR_NOTICE_TEXT`) are also set in the workflow; copy `frontend/.env.example` for local development.

**Documentation:** GitHub Pages deployment; custom domain is set via CNAME in the workflow.
