# backend

FastAPI backend for the Growth Chat AI-powered lead qualification widget. Exposes a streaming `POST /chat` endpoint via Server-Sent Events and integrates with the Anthropic API (Claude Haiku 4.5), LangGraph orchestration, and a Neon PostgreSQL database.

## Requirements

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) — managed via the root workspace

## Setup

```bash
# From the project root — installs all workspace members
uv sync

# Create a .env file in this directory
cp backend/.env.example backend/.env   # then fill in the values
```

### Environment variables

| Variable | Required | Description |
| --- | --- | --- |
| `APP_ENV` | No (default: `development`) | Set to `production` or `staging` to enable the PostgreSQL checkpointer and disable `/docs`. |
| `ZGC_API_KEY` | Yes | Static key issued to each widget deployment. Must match the `ZGC-API-KEY` header sent by the frontend. |
| `LLM_STREAM_TIMEOUT_MS` | No (default: `10000`) | Max milliseconds to wait for the first LLM token before emitting a `STREAM_TIMEOUT` error event. |
| `CHECKPOINT_DB_URL` | Staging/prod only | Neon PostgreSQL connection string. Required when `APP_ENV` is not `development`; the LangGraph `AsyncPostgresSaver` is created and its schema is migrated at startup. |
| `SLACK_WEBHOOK_URL` | Phase 3+ | Incoming webhook URL for the `#new-leads` channel. |
| `SLACK_BOT_TOKEN` | Phase 3+ | Bot token used to update Slack messages after CRM record creation. |
| `FALLBACK_EMAIL_ADDRESS` | Phase 3+ | Internal `sales@` address for last-resort handoff delivery. |
| `SMTP_HOST` | Phase 3+ | SMTP server host. |
| `SMTP_PORT` | No (default: `587`) | SMTP server port. |
| `SMTP_USERNAME` | Phase 3+ | SMTP authentication username. |
| `SMTP_PASSWORD` | Phase 3+ | SMTP authentication password. |

## Development

Start the local database first (see [`data/database/README.md`](../data/database/README.md)):

```bash
cp data/database/.env.example data/database/.env
docker compose up -d
uv run --package database python -m database.migrate
```

Then start the dev server:

```bash
# From project root
uv run --package backend uvicorn backend.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### Running tests

```bash
# Unit tests (no running server required)
uv run --package backend pytest backend/tests/ --ignore=backend/tests/acceptance -v

# Acceptance tests (requires a running server on port 8000)
uv run --package backend pytest backend/tests/acceptance/ -v

# Or against a different target
BACKEND_URL=https://staging.example.com uv run --package backend pytest backend/tests/acceptance/ -v
```

## Docker

The image is built with a two-stage Dockerfile. Run all commands from the **project root** (the build context must include the uv workspace).

### Build

```bash
docker build -f backend/Dockerfile -t growth-chat-backend .
```

### Run

```bash
docker run --env-file backend/.env -p 8080:8080 growth-chat-backend
```

The API is available at `http://localhost:8080`. Interactive docs (`/docs`, `/redoc`) are **disabled** in the container because `APP_ENV=production` is set in `fly.toml` — override with `-e APP_ENV=development` to re-enable them locally.

Liveness: `GET /health` → `{"status": "ok"}` (always 200 once the process is up)
Readiness: `GET /ready` → `{"status": "ready"}` (503 until lifespan completes; used as the Fly.io health check)

## Deployment

The backend is deployed to Fly.io (Frankfurt region). Configuration lives in `backend/fly.toml` — auto-scales to 0 machines when idle, max 1 VM, `shared-cpu-1x`, 256 MB memory.

**Production port:** 8080 (differs from the dev port 8000).

CI/CD deploys automatically on push to `main` when `backend/`, `shared/`, `data/`, `pyproject.toml`, or `uv.lock` change. Required GitHub secret: `FLY_API_TOKEN` (in the `production` environment).

---

## API

### `GET /health`

Returns `{"status": "ok"}` unconditionally. Used by Fly.io as the liveness check.

### `GET /ready`

Returns `{"status": "ready"}` (200) once the lifespan has completed — i.e. the LangGraph graph and checkpointer are initialised. Returns `{"status": "not_ready"}` (503) before that. Used as a readiness probe.

### `POST /chat`

Accepts a visitor message and returns a streaming SSE response.

**Required headers:**

```text
Content-Type: application/json
Accept: text/event-stream
ZGC-Session-ID: <uuid-v4>
ZGC-API-KEY: <static key>
```

**Body:**

```json
{ "message": "string (1–2000 chars)" }
```

**SSE event types:**

| Type | Description |
| --- | --- |
| `token` | One LLM response token — append to displayed message |
| `done` | Turn complete — carries session metadata for analytics |
| `error` | Turn-level failure — session continues |

**Example:**

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -H "ZGC-Session-ID: $(uuidgen)" \
  -H "ZGC-API-KEY: your-dev-key" \
  -d '{"message": "Tell me about your services"}'
```

## Package structure

```text
src/backend/
├── main.py              # FastAPI app, lifespan (checkpointer + graph), /health, /ready
├── config.py            # Environment variable settings (pydantic-settings)
├── limiter.py           # slowapi Limiter — keyed on ZGC-Session-ID (20 req / 5 min)
├── conversation/        # Chat session and SSE streaming
│   ├── graph.py         # LangGraph StateGraph + build_graph(checkpointer) factory
│   ├── models.py        # Request/response models, SessionState, SSE event types
│   └── router.py        # POST /chat route handler
├── qualification/       # Lead scoring and classification
│   └── models.py        # LeadLevel, FitLevel, QualificationState
├── knowledge/           # RAG retrieval interface
│   └── retrieval.py     # retrieve_knowledge() stub — wired as LangGraph tool in Phase 2
├── handoff/             # Lead delivery to sales
│   ├── models.py        # HandoffRequest, CRMLeadPayload, LeadCreationResult
│   ├── business_hours.py  # is_business_hours() — Mon–Fri 09:00–18:00 CET/CEST
│   ├── crm.py           # CRMClient protocol + PostgresCRMClient stub
│   └── delivery.py      # dispatch_handoff() stub — Slack + CRM + email fallback
└── analytics/           # Event tracking
    └── events.py        # AnalyticsEvent, emit_event() stub
```

## Implementation status

| Component | Status | Notes |
| --- | --- | --- |
| `POST /chat` route | Phase 1 complete | LangGraph graph wired; SSE token streaming active; fixed response (Phase 2 replaces with real LLM) |
| `GET /health` | Complete | Always returns `{"status": "ok"}` |
| `GET /ready` | Complete | Returns 503 until lifespan completes |
| Rate limiting | Complete | slowapi — 20 requests / 5 min per session ID |
| LangGraph + MemorySaver | Complete | Local dev checkpointer; graph built during lifespan |
| LangGraph + AsyncPostgresSaver | Complete | Staging/prod; `setup()` called at startup when `APP_ENV != development` |
| Header validation | Complete | 400 / 401 per TRD spec |
| `retrieve_knowledge` | Stub | Raises `NotImplementedError` — wired in Phase 2 |
| `dispatch_handoff` | Stub | Raises `NotImplementedError` — implemented in Phase 3 |
| `PostgresCRMClient` | Stub | Raises `NotImplementedError` — implemented in Phase 3 |
| `emit_event` | Stub | Raises `NotImplementedError` — implemented in Phase 2 |
| `is_business_hours` | Complete | Pure function, no external deps |
