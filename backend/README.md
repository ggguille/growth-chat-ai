# backend

FastAPI backend for the Growth Chat AI-powered lead qualification widget. Exposes a single streaming `POST /chat` endpoint via Server-Sent Events and integrates with the Anthropic API (Claude Haiku 4.5), LangGraph orchestration, and a Neon PostgreSQL database.

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
| `ZGC_API_KEY` | Yes | Static key issued to each widget deployment. Must match the `ZGC-API-KEY` header sent by the frontend. |
| `LLM_STREAM_TIMEOUT_MS` | No (default: `10000`) | Max milliseconds to wait for the first LLM token before emitting a `STREAM_TIMEOUT` error event. |
| `DATABASE_URL` | Yes | Neon PostgreSQL connection string (`postgresql+asyncpg://...`). |
| `SLACK_WEBHOOK_URL` | Yes | Incoming webhook URL for the `#new-leads` channel. |
| `SLACK_BOT_TOKEN` | Yes | Bot token used to update Slack messages after CRM record creation. |
| `HANDOFF_FALLBACK_EMAIL` | Yes | Internal `sales@` address for last-resort handoff delivery. |
| `SMTP_HOST` | Yes | SMTP server host. |
| `SMTP_PORT` | No (default: `587`) | SMTP server port. |
| `SMTP_USER` | Yes | SMTP authentication username. |
| `SMTP_PASSWORD` | Yes | SMTP authentication password. |

## Development

```bash
# Dev server with hot reload (from project root)
uv run --package backend uvicorn backend.main:app --reload --port 8000

# Or from the backend/ directory
uv run uvicorn backend.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

## Docker

The image is built with a two-stage Dockerfile. Run all commands from the **project root** (the build context must include the uv workspace).

### Build

```bash
docker build -f backend/Dockerfile -t growth-chat-backend .
```

### Run

```bash
docker run --env-file backend/.env -p 8000:8000 growth-chat-backend
```

The API is available at `http://localhost:8000`. Interactive docs (`/docs`, `/redoc`) are **disabled** in the container because `APP_ENV=production` is baked into the image — set `APP_ENV=development` in your env file to re-enable them.

Health check: `GET /health` → `{"status": "ok"}`

---

## API

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
├── main.py              # FastAPI app entry point
├── config.py            # Environment variable settings
├── conversation/        # Chat session and SSE streaming
│   ├── models.py        # Request/response Pydantic models
│   └── router.py        # POST /chat route handler
├── qualification/       # Lead scoring and classification
│   └── models.py        # LeadLevel, FitLevel, QualificationState
├── knowledge/           # RAG retrieval interface
│   └── retrieval.py     # retrieve_knowledge() — wired to LangGraph tool
├── handoff/             # Lead delivery to sales
│   ├── models.py        # HandoffRequest, CRMLeadPayload, LeadCreationResult
│   ├── business_hours.py  # is_business_hours() — Mon–Fri 09:00–18:00 CET/CEST
│   ├── crm.py           # CRMClient protocol + PostgresCRMClient
│   └── delivery.py      # dispatch_handoff() — Slack + CRM + email fallback
└── analytics/           # Event tracking
    └── events.py        # AnalyticsEvent, emit_event()
```

## Implementation status

| Component | Status | Notes |
| --- | --- | --- |
| `POST /chat` route | Stub | Returns a static `done` event; orchestrator not yet wired |
| `retrieve_knowledge` | Stub | Raises `NotImplementedError` |
| `dispatch_handoff` | Stub | Raises `NotImplementedError` |
| `PostgresCRMClient` | Stub | Raises `NotImplementedError` |
| `emit_event` | Stub | Raises `NotImplementedError` |
| `is_business_hours` | Complete | Pure function, no external deps |
| Header validation | Complete | 400 / 401 / 422 per TRD spec |
