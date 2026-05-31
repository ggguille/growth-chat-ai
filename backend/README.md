# backend

FastAPI backend for the Growth Chat AI-powered lead qualification widget. Exposes a streaming `POST /chat` endpoint via Server-Sent Events. Runs a 6-node LangGraph conversation agent that qualifies visitors across four dimensions (problem, authority, company, timing), retrieves from a pgvector knowledge base, and proposes handoffs when a lead threshold is reached.

**LLM:** Ollama (Llama 3.1 8B) in local development — Anthropic Claude Haiku 4.5 in production (ADR-001).

## Requirements

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) — managed via the root workspace
- [Ollama](https://ollama.com/) with `llama3.1:8b` pulled — for local development

## Setup

```bash
# From the project root — installs all workspace members
uv sync

# Create a .env file in this directory
cp backend/.env.example backend/.env   # then fill in the values
```

### Environment variables

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `APP_ENV` | No | `development` | Set to `production` or `staging` to enable the PostgreSQL checkpointer and disable `/docs`. |
| `ZGC_API_KEY` | Yes | — | Static key issued to each widget deployment. Must match the `ZGC-API-KEY` header sent by the frontend. |
| `ANTHROPIC_API_KEY` | Prod/staging | — | Anthropic API key for Claude Haiku 4.5. Not required in development (Ollama is used instead). |
| `ANTHROPIC_MODEL` | No | `claude-haiku-4-5-20251001` | Anthropic model identifier. |
| `OLLAMA_MODEL` | No | `llama3.1:8b` | Ollama model for local development (ADR-001). |
| `OLLAMA_BASE_URL` | No | `http://localhost:11434` | Ollama server URL. |
| `LLM_STREAM_TIMEOUT_MS` | No | `10000` | Max milliseconds to wait for the first LLM token. |
| `RAG_RELEVANCE_THRESHOLD` | Prod/staging | — | Minimum cosine similarity score for a knowledge chunk to be included in results. Set to `0.70` provisionally in dev; tune in Phase 4. Service will not start in non-development environments if unset. |
| `RAG_TOP_K` | No | `5` | Maximum number of knowledge chunks returned per retrieval. |
| `KNOWLEDGE_TABLE_NAME` | No | `knowledge_chunks` | pgvector table name. Use `knowledge_chunks_dev` locally (384-dim HuggingFace embeddings). |
| `OPENAI_API_KEY` | Prod/staging | — | OpenAI API key for `text-embedding-3-small` query embeddings. When empty, HuggingFace `all-MiniLM-L6-v2` is used locally. |
| `STALL_TURN_THRESHOLD` | No | `6` | Number of turns without a Stage 3 proposal before the stall path fires. |
| `CONTEXT_WINDOW_TURNS` | No | `10` | Number of exchange pairs retained in the LLM sliding window. |
| `BUSINESS_HOURS_TIMEZONE` | Prod/staging | — | IANA timezone identifier for the team (e.g. `Europe/Madrid`). Service will not start in non-development environments if unset. |
| `CHECKPOINT_DB_URL` | Prod/staging | — | Neon PostgreSQL connection string. Required when `APP_ENV` is not `development`. |
| `SLACK_WEBHOOK_URL` | Phase 3+ | — | Incoming webhook URL for the `#new-leads` channel. |
| `SLACK_BOT_TOKEN` | Phase 3+ | — | Bot token used to update Slack messages after CRM record creation. |
| `FALLBACK_EMAIL_ADDRESS` | Phase 3+ | — | Internal `sales@` address for last-resort handoff delivery. |
| `SMTP_HOST` | Phase 3+ | — | SMTP server host. |
| `SMTP_PORT` | No | `587` | SMTP server port. |
| `SMTP_USERNAME` | Phase 3+ | — | SMTP authentication username. |
| `SMTP_PASSWORD` | Phase 3+ | — | SMTP authentication password. |

## Development

Start the local database first (see [`data/database/README.md`](../data/database/README.md)):

```bash
cp data/database/.env.example data/database/.env
docker compose up -d
uv run --package database python -m database.migrate
```

Start Ollama with Llama 3.1 8B (first run downloads ~5 GB):

```bash
ollama pull llama3.1:8b
ollama serve
```

Then start the dev server:

```bash
# From project root
uv run --package backend uvicorn backend.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

On startup the server logs which LLM backend is selected:

```text
INFO  LLM backend: Ollama (llama3.1:8b @ http://localhost:11434)
```

### Running tests

```bash
# Unit tests (no running server required — LLM client is mocked)
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

**Required Fly.io secrets (set once):**

```bash
flyctl secrets set \
  ZGC_API_KEY=<key> \
  ANTHROPIC_API_KEY=<key> \
  RAG_RELEVANCE_THRESHOLD=0.70 \
  BUSINESS_HOURS_TIMEZONE=Europe/Madrid \
  CHECKPOINT_DB_URL=<neon-connection-string> \
  --config backend/fly.toml
```

> **Launch note — embedding model and table must match.**
>
> The shared `get_embeddings()` factory (`shared/knowledge_base`) picks the embedding model based on whether `OPENAI_API_KEY` is set:
>
> - **No key** → HuggingFace `all-MiniLM-L6-v2` (384-dim) → query must target `knowledge_chunks_dev`
> - **Key present** → OpenAI `text-embedding-3-small` (1536-dim) → query must target `knowledge_chunks`
>
> `KNOWLEDGE_TABLE_NAME` defaults to `knowledge_chunks`. **Until the production ingestion pipeline is in place** (OpenAI embeddings, `knowledge_chunks` table), add these two secrets so the backend queries the populated dev table:
>
> ```bash
> flyctl secrets set \
>   KNOWLEDGE_TABLE_NAME=knowledge_chunks_dev \
>   --config backend/fly.toml
> ```
>
> Do **not** set `OPENAI_API_KEY` while using `knowledge_chunks_dev` — mismatched dimensions (1536 vs 384) will cause pgvector to return no results. When switching to production embeddings: set `OPENAI_API_KEY`, remove the `KNOWLEDGE_TABLE_NAME` override (or set it to `knowledge_chunks`), and run the production ingestion pipeline first.

---

## API

### `GET /health`

Returns `{"status": "ok"}` unconditionally. Used by Fly.io as the liveness check.

### `GET /ready`

Returns `{"status": "ready"}` (200) once the lifespan has completed — i.e. the LangGraph graph and checkpointer are initialised. Returns `{"status": "not_ready"}` (503) before that. Used as a readiness probe.

### `POST /chat`

Accepts a visitor message and returns a streaming SSE response. The agent runs the full 6-node graph per turn: qualification extraction → lead scoring → response generation (with optional RAG retrieval) → stall detection → (optional) Stage 3 proposal.

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

| Type | Payload | Description |
| --- | --- | --- |
| `token` | `{ content: string }` | One LLM response token — append to displayed message |
| `done` | `{ session_id, lead_level, current_stage, stage3_proposal_issued, handoff_reason, turn_count }` | Turn complete — carries live qualification state |
| `error` | `{ code, message }` | Turn-level failure — session continues |

`done.lead_level` values: `"hot"` / `"warm"` / `"cold"`.  
`done.handoff_reason` values: `"hot_lead"` / `"explicit_request"` / `"stall"` / `"llm_failure"` / `null`.

**Example:**

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -H "ZGC-Session-ID: $(uuidgen)" \
  -H "ZGC-API-KEY: dev-key" \
  -d '{"message": "We are building a RAG pipeline and need experienced engineers"}'
```

## Package structure

```text
src/backend/
├── main.py              # FastAPI app, lifespan (LLM client + checkpointer + graph), /health, /ready
├── config.py            # Environment variable settings (pydantic-settings)
├── limiter.py           # slowapi Limiter — keyed on ZGC-Session-ID (20 req / 5 min)
├── llm/                 # LLM backend abstraction (ADR-001)
│   ├── base.py          # BaseLLMClient ABC — complete(), structured_complete(), stream()
│   ├── anthropic_client.py  # Production: Claude Haiku 4.5 via Anthropic API
│   ├── ollama_client.py     # Development: Llama 3.1 8B via Ollama
│   └── factory.py       # create_llm_client(settings) — selects backend by APP_ENV
├── conversation/        # Chat session orchestration and SSE streaming
│   ├── graph.py         # 6-node LangGraph StateGraph — update_state, score_router,
│   │                    #   generate_response, stall_check, propose_handoff, write_state
│   ├── models.py        # GraphState TypedDict (full TRD schema), SSE event models, ChatRequest
│   ├── prompt.py        # 9-layer system prompt builder (CDD §8.3) — build_system_prompt(),
│   │                    #   build_proposal_prompt()
│   └── router.py        # POST /chat — streams via graph.astream_events()
├── qualification/       # Lead scoring and classification
│   └── models.py        # LeadLevel, FitLevel, QualificationState, SignalEntry,
│                        #   QualificationDelta, derive_lead_level()
├── knowledge/           # RAG retrieval
│   └── retrieval.py     # retrieve_knowledge() — pgvector cosine search; OpenAI embeddings
│                        #   (prod) / HuggingFace all-MiniLM-L6-v2 (dev)
├── handoff/             # Lead delivery to sales
│   ├── models.py        # HandoffRequest, CRMLeadPayload, LeadCreationResult
│   ├── business_hours.py  # is_business_hours(same_day_followup) — Mon–Fri 09:00–18:00 CET/CEST;
│   │                    #   next_business_day_opening()
│   ├── crm.py           # CRMClient protocol + PostgresCRMClient (Phase 3)
│   └── delivery.py      # dispatch_handoff() — no-op stub (Phase 3: Slack + CRM + email)
└── analytics/           # Event tracking
    └── events.py        # AnalyticsEvent, emit_event() — no-op stub (Phase 3)
```

## Implementation status

| Component | Status | Notes |
| --- | --- | --- |
| `POST /chat` route | ✅ Phase 2 complete | Real AI agent — qualification, RAG, Stage 3 proposals |
| `GET /health` | ✅ Complete | Always returns `{"status": "ok"}` |
| `GET /ready` | ✅ Complete | Returns 503 until lifespan completes |
| Rate limiting | ✅ Complete | slowapi — 20 requests / 5 min per session ID |
| LLM abstraction layer | ✅ Phase 2 complete | Ollama (dev) / Anthropic Claude Haiku 4.5 (prod) |
| 6-node LangGraph graph | ✅ Phase 2 complete | `update_state`, `score_router`, `generate_response`, `stall_check`, `propose_handoff`, `write_state` |
| System prompt (9 layers) | ✅ Phase 2 complete | All 27 CDD prohibited behaviours encoded; dynamic qualification state injected per turn |
| Qualification state machine | ✅ Phase 2 complete | Monotonic confidence transitions; `derive_lead_level()`; P3 referral pattern |
| `retrieve_knowledge` | ✅ Phase 2 complete | pgvector cosine search; OpenAI / HuggingFace embedding switch |
| Business hours detection | ✅ Complete | `same_day_followup` param; `next_business_day_opening()` |
| LangGraph + MemorySaver | ✅ Complete | Local dev checkpointer |
| LangGraph + AsyncPostgresSaver | ✅ Complete | Staging/prod; `setup()` called at startup |
| `dispatch_handoff` | ⏳ Phase 3 | No-op stub — Slack + CRM + email fallback |
| `PostgresCRMClient` | ⏳ Phase 3 | No-op stub — `leads` table insert |
| `emit_event` | ⏳ Phase 3 | No-op stub — analytics pipeline |
