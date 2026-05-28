# Growth Chat

AI Chat project to learn about AI engineering

## Requirements

### NodeJS + NVM

This project uses **[NodeJS](https://nodejs.org/es)** for documentation, version managed by **[NVM](https://github.com/nvm-sh/nvm)**

### Python + uv

The backend uses **Python 3.14+**, managed via **[uv](https://docs.astral.sh/uv/)** as a workspace.

## Documentation

All documentation about project is in `./documentation` folder.

Based on **[docmd framework](https://docs.docmd.io/)**

### Commands

```bash
# Move to documentation directory
cd ./documentation

# Start project on local
npx docmd dev

# Build project
npx docmd build
```

## Database

Local development uses a Postgres container with the pgvector extension. Start it, then apply migrations before running the backend.

```bash
# Configure and start local Postgres (pgvector/pgvector:pg16)
cp data/database/.env.example data/database/.env
docker compose up -d

# Apply all pending migrations
uv run --package database python -m database.migrate
```

See [`data/database/README.md`](./data/database/README.md) for rollback, seeds, and CI/CD setup.

## Ingestion

Knowledge base ingestion pipeline in `./data/ingestion` — chunks Markdown documents, generates embeddings, and upserts them into the pgvector store. In dev mode it uses a local HuggingFace model (no API key needed).

Source documents live in `./data/knowledge-base/`.

```bash
# Ensure Docker Compose is running and migrations are applied (see Database above)

# Copy env file and configure connection string
cp data/ingestion/.env.example data/ingestion/.env

# Run the dev ingestion pipeline
uv run --package ingestion python -m ingestion.pipeline --source data/knowledge-base
```

See [`data/ingestion/README.md`](./data/ingestion/README.md) for environment variables and embedding model details.

## Backend

FastAPI backend in `./backend` — streaming `POST /chat` endpoint via SSE, with LangGraph orchestration, RAG retrieval, and lead handoff delivery.

### Commands

```bash
# Install all workspace dependencies (from project root)
uv sync

# Start dev server with hot reload (database must be running — see above)
uv run --package backend uvicorn backend.main:app --reload --port 8000

# Run unit tests
uv run --package backend pytest backend/tests/ --ignore=backend/tests/acceptance -v
```

See [`backend/README.md`](./backend/README.md) for environment variables, full API docs, and acceptance tests.

## Frontend

React + TypeScript chat widget in `./frontend`, built as a `<growth-chat>` Web Component with Shadow DOM. Streams responses from the backend via SSE, with GDPR consent flow and automatic fallback when the backend is unavailable.

### Commands

```bash
# Move to frontend directory
cd ./frontend

# Start dev server with HMR
npm run dev

# Build self-contained IIFE bundle to dist/chat.js
npm run build

# Run tests (vitest)
npm test
```

### Embed on any page

```html
<script src="<CDN_URL>/chat.js" defer></script>
<growth-chat
  api-url="<API_URL>"
  fallback-url="<CONTACT_URL>"
  api-key="<API_KEY>"
  data-gdpr-text="This chat is powered by AI…"
></growth-chat>
```

See [`frontend/README.md`](./frontend/README.md) for all attributes, custom events, and demo instructions.

## CI/CD

Three automated pipelines deploy each module on push to `main`. All support manual runs via `workflow_dispatch`. See `.github/workflows/` for full details.

| Workflow | Trigger paths | Deploys to |
| --- | --- | --- |
| `deploy-backend.yml` | `backend/`, `shared/`, `data/`, `pyproject.toml`, `uv.lock` | Fly.io |
| `deploy-frontend.yml` | `frontend/` | Fly Tigris object storage (CDN) |
| `deploy-documentation.yml` | `documentation/` | GitHub Pages |

### Required GitHub secrets

The following secrets must be set in the `production` GitHub environment:

| Secret | Workflow | Purpose |
| --- | --- | --- |
| `FLY_API_TOKEN` | deploy-backend | Fly.io authentication |
| `CHECKPOINT_DB_URL` | deploy-backend | Neon PostgreSQL connection string for pre-deploy migrations |
| `TIGRIS_ACCESS_KEY_ID` | deploy-frontend | Object storage write access |
| `TIGRIS_SECRET_ACCESS_KEY` | deploy-frontend | Object storage write access |
