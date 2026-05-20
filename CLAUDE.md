# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Growth Chat is an AI engineering learning project structured as a monorepo with four modules:

- `documentation/` — DocMD static site (implemented)
- `backend/` — FastAPI backend with SSE streaming and domain-driven structure (scaffolded)
- `frontend/` — React + TypeScript + Vite chat widget (scaffolded)
- `evaluation/`, `knowledge_ingest/`, `shared/` — Python uv workspace members (stubs)

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

## Frontend Module

All commands run from `frontend/`:

```bash
npm run dev    # dev server with HMR at localhost:5173
npm run build  # type-check + IIFE bundle to dist/chat.js
```

The widget is a `<growth-chat>` Custom Element (Web Component) that mounts React inside a Shadow DOM. `src/GrowthChat.ts` is the wrapper; `src/components/ChatWidget.tsx` is the React component. `vite build` produces a single self-contained `dist/chat.js` IIFE for CDN distribution.

## Architecture Notes

- The uv workspace root is `pyproject.toml`. Members: `backend`, `evaluation`, `knowledge-ingest`, `shared/knowledge_base`.
- Code is organised by business domain, not technical layer (conversation, qualification, knowledge, handoff, analytics).
- Each module is independent; there is no root-level build system.
- The `backend/` package uses src layout (`src/backend/`). Import as `from backend.x import y`.

## CI/CD and Deployment

Three workflows in `.github/workflows/`: `deploy-backend.yml`, `deploy-frontend.yml`, `deploy-documentation.yml`. All trigger on push to `main` and support `workflow_dispatch` for manual runs.

Required secrets — must be set in the `production` GitHub environment:

- `FLY_API_TOKEN` — authenticates Docker push and Fly.io deploy (backend)
- `TIGRIS_ACCESS_KEY_ID` / `TIGRIS_SECRET_ACCESS_KEY` — S3-compatible credentials for Fly Tigris object storage (frontend)

**Backend:** Production runs on port **8080** (dev uses 8000). Fly.io config is `backend/fly.toml` (Frankfurt region, auto-scale to 0, `shared-cpu-1x`, 256 MB). Docker build context must be the **project root** so the uv workspace is available:

```bash
docker build -f backend/Dockerfile -t growth-chat-api .
```

**Frontend:** Build artifact is `dist/chat.js` (single IIFE). The CI workflow uploads it to Fly Tigris object storage with a 1-hour cache TTL. CDN bucket name and endpoint URL live in the workflow env vars — not in source. Required build-time env vars (`VITE_API_URL`, `VITE_FALLBACK_URL`, `VITE_GDPR_NOTICE_TEXT`) are also set in the workflow; copy `frontend/.env.example` for local development.

**Documentation:** GitHub Pages deployment; custom domain is set via CNAME in the workflow.
