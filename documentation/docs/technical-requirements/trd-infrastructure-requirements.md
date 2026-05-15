---
description: "TRD Section 6 — Infrastructure Requirements: compute, storage, backup, networking, and consolidated environment variable reference for the AI-powered lead qualification chat."
---

# Infrastructure Requirements

> **Decisions that informed this section:** ADR-006 (Fly.io + Neon + Cloudflare)

---

## Compute

All runtime compute is provided by **Fly.io** (`fra`, Frankfurt). There are two distinct runtime workloads: the Chat API (always-on, request-driven) and the daily backup job (scheduled, short-lived).

### Chat API Machine

| Parameter | Value |
| --- | --- |
| Provider | Fly.io Machines |
| Region | `fra` (Frankfurt, EU) |
| Size | `shared-cpu-1x`, 256 MB RAM |
| Autoscale-to-zero | Enabled — Machine suspends after 5 minutes of inactivity |
| Min instances | `0` (MVP) — cold start latency is acceptable for low-traffic periods |
| Max instances | `1` (MVP) — horizontal scaling not required until load testing in Phase 5 warrants it |
| Exposed port | `8080` (internal); Cloudflare terminates TLS on `443` externally |

**Cold start behaviour.** When the Machine is suspended and a new request arrives, Fly.io wakes it in approximately 300–500ms. The Chat API then takes an additional ~200ms to initialise the FastAPI application and the LangGraph checkpointer connection. Total cold start: ~500–700ms. This is within the TTFT budget (p95 < 3s, Section 7) for first-turn requests. Subsequent turns in the same session are served from a warm Machine.

**Scaling review trigger.** If Phase 5 load testing reveals that a single Machine instance cannot sustain the target p95 TTFT under concurrent load, `min_machines_running = 1` (disable scale-to-zero) and `max_machines = 2` are the first configuration changes. No code changes are required. See ADR-006 — Review Triggers.

### Backup Cron Machine

| Parameter | Value |
| --- | --- |
| Provider | Fly.io Machines (scheduled) |
| Region | `fra` (Frankfurt, EU) |
| Size | `shared-cpu-1x`, 256 MB RAM |
| Schedule | Daily at 02:00 CET/CEST |
| Runtime | Single-execution — Machine starts, runs `pg_dump`, uploads to Tigris, exits |

The backup Machine shares the `DATABASE_URL` secret with the Chat API Machine. It requires three additional secrets: `TIGRIS_BUCKET_NAME`, `TIGRIS_ACCESS_KEY_ID`, and `TIGRIS_SECRET_ACCESS_KEY`. See the Environment Variables section and the deployment runbook.

### Indexing Pipeline

The knowledge base indexing pipeline (document chunking, embedding, pgvector
insertion) runs as a **one-off Fly Machine** invoked manually during Phase 2
and whenever the knowledge base is updated. It is not a persistent service.
It uses the same container image as the Chat API, invoked with a different
entrypoint (`python -m scripts.index`).

---

## Storage

All persistent storage is provided by **Neon Serverless Postgres**
(`eu-central-1`, Frankfurt) on the free tier. The database serves two roles:
pgvector knowledge index (ADR-003) and LangGraph session state checkpointer
(ADR-004). Both roles share the same Neon project and connection string in v1.

### Database Tables and Sizing

| Table | Role | Estimated MVP size | Retention |
| --- | --- | --- | --- |
| `knowledge_chunks` | pgvector knowledge index | ~500 chunks × ~512 tokens ≈ 2 MB | Indefinite — static content |
| `checkpoints` | LangGraph session state (latest) | ~1 KB per active session | 90 days from last activity |
| `checkpoint_writes` | LangGraph write-ahead log | ~2 KB per session turn | 90 days from last activity |
| `handoff_records` | Human handoff audit trail | ~5 KB per handoff event | Indefinite — or until GDPR erasure request |
| `messages` | Conversation message log | ~1 KB per message | 90 days from session close |

**Total estimated MVP storage: < 50 MB.** This is well within Neon's free tier
limit of 512 MB.

**Retention enforcement.** A scheduled cleanup job (co-located with the backup
cron Machine, running weekly) deletes rows from `checkpoints`,
`checkpoint_writes`, and `messages` where the associated session's
`closed_at` timestamp is older than 90 days. `handoff_records` are retained
indefinitely and deleted only on explicit GDPR erasure requests processed
manually by the data controller.

### pgvector Index

| Parameter | Value |
| --- | --- |
| Extension | `pgvector` — installed via `CREATE EXTENSION vector` |
| Index type | HNSW |
| Distance metric | Cosine similarity |
| `m` (HNSW build parameter) | `16` (appropriate for corpora < 100K vectors) |
| `ef_construction` | `64` |
| `ef_search` | Configurable via `RAG_HNSW_EF_SEARCH` (default: `40`) |

### Backup Strategy

Neon free tier provides 24-hour point-in-time recovery (PITR). The PRD
requires 90-day retention of conversation data (§6.3). To bridge this gap,
a daily `pg_dump` backup is written to Tigris object storage.

**Backup process:**

1. The backup cron Machine runs daily at 02:00 CET/CEST.
2. It executes `pg_dump` against the Neon database, compressing output with
   `gzip`.
3. The compressed archive is uploaded to the `backups/` prefix in the
   configured Tigris bucket, named `backup-YYYY-MM-DD.sql.gz`.
4. Tigris object lifecycle policy retains archives for **90 days**, then
   deletes automatically.

**Recovery procedure.** In the event of data loss beyond the 24-hour PITR
window, the on-call engineer downloads the most recent daily archive from
Tigris, restores it to a new Neon database branch, and updates
`CHECKPOINT_DB_URL` to point to the restored branch.

**Accepted risk.** Up to 24 hours of conversation data may be lost in a
catastrophic failure scenario (hardware loss beyond PITR coverage). This is
an accepted risk for the MVP. If the system enters production under formal
SLA commitments, upgrading to Neon Launch plan (~$19/month, 7-day PITR) is
the remediation path. See ADR-006 — Review Triggers.

**Backup failure alerting.** If the backup cron Machine exits with a non-zero
code, Fly.io emits a machine exit event. This event must be routed to the
observability layer (Section 9) as a `backup_failed` alert. Configuration
of this alert is part of the Phase 3 observability setup.

### Static Asset Storage

The compiled `chat.js` widget bundle is stored in **Tigris** (Fly-native
S3-compatible object storage) and served via Cloudflare CDN. The widget
bundle contains no personal data and is not subject to GDPR retention rules.

---

## Networking

### TLS

| Segment | TLS | Notes |
| --- | --- | --- |
| Visitor browser → Cloudflare | TLS 1.3 | Terminated by Cloudflare; minimum TLS 1.2 enforced via Cloudflare SSL/TLS settings |
| Cloudflare → Fly Machine | TLS 1.2+ | Cloudflare Full (Strict) mode — Fly Machine must present a valid certificate |
| Fly Machine → Neon | TLS 1.3 | Neon requires TLS on all connections; enforced via `sslmode=require` in `DATABASE_URL` |
| Fly Machine → Anthropic API | TLS 1.3 | Standard HTTPS to `api.anthropic.com` |
| Fly Machine → OpenAI API | TLS 1.3 | Standard HTTPS to EU endpoint (see `OPENAI_EU_ENDPOINT`) |
| Fly Machine → Slack webhook | TLS 1.3 | Standard HTTPS to `hooks.slack.com` |

### CORS

The Chat API must allow cross-origin requests from the host website where the
`<growth-chat>` widget is embedded. CORS is configured at the FastAPI
application level.

```python
# FastAPI CORS configuration
origins = [
    os.environ["ALLOWED_ORIGIN"],   # e.g. "https://www.company.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type", "X-Widget-Token"],
)
```

`ALLOWED_ORIGIN` is a required environment variable (see Section 6.4). Wildcard
origins (`*`) must not be used in staging or production — only in local
development.

### Client IP Resolution

Cloudflare proxies all inbound traffic. The Fly Machine sees Cloudflare's
egress IP in the socket, not the visitor's IP. The Chat API must read the
`CF-Connecting-IP` header as the authoritative client IP for per-IP rate
limiting in `slowapi`.

```python
def get_client_ip(request: Request) -> str:
    return request.headers.get("CF-Connecting-IP") or request.client.host
```

This function is used as the key function in all `slowapi` rate limit
decorators. Using `X-Forwarded-For` is not sufficient — it may contain
multiple IPs in proxy chains.

### Ports and Domains

| Service | Internal port | External | Notes |
| --- | --- | --- | --- |
| Chat API | `8080` | `https://api.[domain]/chat` | Domain TBD — configured in `ALLOWED_ORIGIN` and widget `api-url` attribute |
| Widget CDN | — | `https://cdn.[domain]/chat.js` | Served by Cloudflare from Tigris origin |
| Neon | `5432` | Not exposed publicly | Accessed from Fly Machine via `DATABASE_URL` |

Production domain names are defined at deployment time and documented in the
deployment runbook. They are not hardcoded in the application.

---

## Environment Variables

This section is the single authoritative reference for all environment
variables consumed by the system. Variables are grouped by the component that
reads them. All variables marked **Required** cause the service to refuse to
start if unset.

> **Secret management.** All variables marked as secrets must be stored in
> Fly.io Secrets (`fly secrets set KEY=value`) and must never be committed to
> source control. Variables marked as build-time are set in the Fly.io build
> environment or as `VITE_*` variables in the widget build pipeline.

---

### LLM — Anthropic

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `ANTHROPIC_API_KEY` | **Yes** | — | Anthropic API authentication key. Secret. |
| `LLM_STREAM_TIMEOUT_MS` | No | `8000` | Maximum milliseconds to wait for the first LLM token before declaring a stream timeout (§3.1) |
| `MAX_TOOL_CALLS_PER_TURN` | No | `1` | Maximum `retrieve_knowledge` invocations per turn; additional calls are ignored and logged (§3.3) |
| `MAX_TOKENS_PER_SESSION` | No | `16000` | Maximum cumulative tokens (input + output) consumed across a session. The orchestrator tracks token usage from the Anthropic API response and refuses new turns once the limit is reached, returning a graceful session-limit message. Exists to bound per-session LLM cost (EC-12). |
| `MONTHLY_COST_CAP_USD` | No | `50` | Soft monthly cost ceiling for Anthropic API spend in USD. Not enforced at the application layer — consumed by the observability layer (Section 9) to configure spend alerting. Declared here for environment consistency. |

---

### RAG — OpenAI Embeddings

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `OPENAI_API_KEY` | **Yes** | — | OpenAI API authentication key. Secret. |
| `OPENAI_EU_ENDPOINT` | No | `https://api.openai.com/v1` | OpenAI API base URL. Set to the EU data residency endpoint in all environments that process EU visitor data (ADR-003). |
| `OPENAI_EMBEDDING_MODEL` | No | `text-embedding-3-small` | OpenAI embedding model identifier (§3.3) |
| `RAG_RELEVANCE_THRESHOLD` | **Yes — no default** | `0.70` *(provisional, Phase 1–2 only)* | Minimum cosine similarity score for a chunk to be included in retrieval results. **Must be tuned in Phase 4 before production deployment.** The service will not start if unset. (EC-05, §3.3) |
| `RAG_PROACTIVE_THRESHOLD` | No | `RAG_RELEVANCE_THRESHOLD + 0.10` | Minimum score for a case study chunk to trigger proactive surfacing (FR-18, §3.3) |
| `RAG_TOP_K` | No | `5` | Maximum number of chunks returned per retrieval call |
| `RAG_HNSW_EF_SEARCH` | No | `40` | HNSW `ef_search` parameter — query-time recall/latency trade-off (§3.3) |
| `CHUNK_SIZE` | No | `512` | Token size for document chunks at ingestion time |
| `CHUNK_OVERLAP` | No | `64` | Token overlap between adjacent chunks at ingestion time |
| `KNOWLEDGE_TABLE_NAME` | No | `knowledge_chunks` | pgvector table name — allows environment-specific tables without schema changes |

---

### Conversation Orchestrator

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `STALL_TURN_THRESHOLD` | No | `6` | Number of turns without a Stage 3 proposal before stall is declared (EC-06, §3.1) |
| `CONTEXT_WINDOW_TURNS` | No | `10` | Number of most recent visitor/assistant exchange pairs retained in the sliding window passed to the LLM. Must be > 0. (EC-13, §3.1) |

---

### Persistence

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `CHECKPOINT_DB_URL` | **Yes** | — | Neon PostgreSQL connection string with `sslmode=require`. Used by both the LangGraph checkpointer (ADR-004) and the Knowledge Retriever (ADR-003). Format: `postgresql+asyncpg://user:password@host/dbname?sslmode=require`. Secret. |
| `SESSION_TTL_HOURS` | No | `24` | Hours after which an inactive session is expired and marked `termination_type = session_expiry` (§3.2) |

---

### Human Handoff Subsystem

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `SLACK_WEBHOOK_URL` | **Yes** | — | Incoming webhook URL for `#new-leads`. Secret. |
| `SLACK_BOT_TOKEN` | **Yes** | — | Slack bot token for `chat.update` — required to add the CRM record button to the Slack message once CRM delivery completes (§3.4, §5.2). Secret. |
| `FALLBACK_EMAIL_ADDRESS` | **Yes** | — | Recipient address for dual-channel failure fallback email (FR-19, §3.4) |
| `SMTP_HOST` | **Yes** | — | SMTP server hostname for fallback email |
| `SMTP_PORT` | No | `587` | SMTP server port |
| `SMTP_USERNAME` | **Yes** | — | SMTP authentication username. Secret. |
| `SMTP_PASSWORD` | **Yes** | — | SMTP authentication password. Secret. |
| `HANDOFF_RETRY_BACKOFF_SECONDS` | No | `1,3,9` | Comma-separated retry wait times in seconds for Slack and CRM delivery (§3.4) |

---

### Business Hours Detection

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `BUSINESS_HOURS_TIMEZONE` | **Yes — no default** | — | IANA timezone identifier for the team's business hours. Must be a valid `zoneinfo` key. Example: `Europe/Madrid`. Service will not start if unset or invalid. (§3.5) |
| `BUSINESS_HOURS_START` | No | `9` | Start of business hours — 24h integer hour, inclusive. Example: `9` = 09:00. |
| `BUSINESS_HOURS_END` | No | `18` | End of business hours — 24h integer hour, exclusive. Example: `18` = up to 17:59:59. Must be > `BUSINESS_HOURS_START`. |
| `BUSINESS_HOURS_SAME_DAY_CUTOFF` | No | `16` | Hour after which same-day follow-up is not offered (FR-22). Example: `16` = after 16:00 CET/CEST. |

---

### Chat API — Application

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `ALLOWED_ORIGIN` | **Yes** | — | CORS allowed origin for the host website. Example: `https://www.company.com`. Must not be `*` in staging or production. |

---

### Backup Cron Machine Variables

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `TIGRIS_BUCKET_NAME` | **Yes** | — | Tigris bucket name for backup archives |
| `TIGRIS_ACCESS_KEY_ID` | **Yes** | — | Tigris S3-compatible access key. Secret. |
| `TIGRIS_SECRET_ACCESS_KEY` | **Yes** | — | Tigris S3-compatible secret key. Secret. |

> `DATABASE_URL` is shared with the Chat API Machine via the same Fly.io app
> secrets and does not need to be declared separately for the backup job.

---

### Widget — Build-time (VITE_*)

These variables are injected at widget build time and compiled into the
`chat.js` bundle. They are not runtime environment variables. They are set
in the CI/CD pipeline environment for each deployment target.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `VITE_API_URL` | **Yes** | — | Chat API streaming endpoint URL. Example: `https://api.[domain]/chat`. Compiled into the widget bundle. |
| `VITE_FALLBACK_URL` | **Yes** | — | URL opened in a new tab when the AI backend is unavailable (EC-07). Example: existing company contact form URL. |
| `VITE_STREAM_TIMEOUT_MS` | No | `10000` | Milliseconds before stream timeout activates widget fallback state (§3.7) |
| `VITE_DEFAULT_PROACTIVE_MESSAGE` | No | `"Have a question about AI engineering?"` | Default proactive prompt text displayed before the visitor sends a first message (§3.7) |
| `VITE_GDPR_NOTICE_TEXT` | **Yes** | — | GDPR data processing notice copy displayed on the first turn. Must be reviewed by legal before production deployment. See §3.7.3 for the required content. |

---

### Quick Reference — Required Variables Checklist

The following variables have no default and cause the service to refuse to
start (or behave incorrectly) if unset. This list is the minimum viable
configuration for a deployment.

**Chat API runtime (Fly secrets):**

```text
ANTHROPIC_API_KEY
OPENAI_API_KEY
RAG_RELEVANCE_THRESHOLD       # provisional: 0.70 for Phase 1-2 only
CHECKPOINT_DB_URL
SLACK_WEBHOOK_URL
SLACK_BOT_TOKEN
FALLBACK_EMAIL_ADDRESS
SMTP_HOST
SMTP_USERNAME
SMTP_PASSWORD
ALLOWED_ORIGIN
BUSINESS_HOURS_TIMEZONE       # example: Europe/Madrid
```

**Backup cron Machine (Fly secrets):**

```text
TIGRIS_BUCKET_NAME
TIGRIS_ACCESS_KEY_ID
TIGRIS_SECRET_ACCESS_KEY
```

**Widget build pipeline (CI environment):**

```text
VITE_API_URL
VITE_FALLBACK_URL
VITE_GDPR_NOTICE_TEXT
```

---

## Engineering Concerns Resolved by This Section

| EC | Concern | Resolution |
| --- | --- | --- |
| EC-05 | RAG relevance threshold — no hardcoded default, must be tuned | `RAG_RELEVANCE_THRESHOLD` is required with no default; provisional value 0.70 for Phase 1–2 dev; tuning process defined in §3.3; production deployment blocked without Phase 4 validation |
| EC-12 | Rate limiting, cost controls, and per-session token budget | `MAX_TOKENS_PER_SESSION` enforces per-session token budget in the orchestrator; `MONTHLY_COST_CAP_USD` is consumed by the observability layer (§9); per-IP rate limiting via Cloudflare Rules (ADR-006) |
| EC-13 | Sliding window size — configurable, not hardcoded | `CONTEXT_WINDOW_TURNS` with default `10`; service refuses to start if set to `0` or negative |
