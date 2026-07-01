---
description: "Operations runbook for the Growth Chat backend API — platform details, health checks, deploy pipeline, rollback, and configuration."
---

# Backend API

The backend is a FastAPI application running on Fly.io. It exposes a single streaming chat endpoint (`POST /chat`) and handles all AI processing, qualification logic, RAG retrieval, and human handoff dispatch server-side.

---

## Platform

| Parameter | Value |
| --- | --- |
| Platform | Fly.io Machines |
| Region | Frankfurt (`fra`) |
| Machine size | `shared-cpu-1x`, 512 MB RAM |
| Instances | 0–1 (auto-scales to zero when idle) |
| Idle suspend | Machine suspends after ~5 minutes of inactivity |
| Cold-start latency | ~500–700 ms (suspend → first request served) |
| Internal port | `8080` |

Cold starts are expected and within the 3-second first-token budget for first-turn requests. Subsequent turns in an active session are served from a warm machine. If sustained low latency under concurrent load becomes a requirement, see ADR-006 for the scaling configuration steps (no code changes required).

---

## Health Endpoints

These endpoints are used by Fly.io's health check system and must not be removed.

| Endpoint | Purpose | Expected response |
| --- | --- | --- |
| `GET /health` | Process liveness — Docker HEALTHCHECK | `{"status": "ok"}` — 200 always, if the process is up |
| `GET /ready` | Application readiness — Fly.io HTTP check | `{"status": "ready"}` — 200 when ready; 503 during startup or shutdown |

Fly.io polls `/ready` every 30 seconds with a 5-second timeout and a 30-second grace period after machine start. Three consecutive failures trigger a machine restart.

OpenAPI docs are available at `/docs` in all environments (disabled at `/redoc` in production).

---

## Request Limits

- **Concurrency:** 20 requests soft limit, 25 hard limit per machine. Requests above the hard limit receive a 503.
- **Rate limiting:** The `/chat` endpoint is rate-limited by session ID (implemented with `slowapi`). Excess requests receive a 429 with a `retry_after_seconds` field.
- **Message length:** 2,000 characters maximum per message.
- **Per-session token budget:** Configurable via environment variable (default 16,000 cumulative tokens). Sessions that exceed the budget receive a graceful closure message.

---

## Deploy Pipeline

**Trigger:** Automatic on push to `main` touching `backend/**`, `shared/**`, `data/**`, `pyproject.toml`, or `uv.lock`.

**Pipeline stages (sequential — each gates the next):**

```text
1. Unit tests          → pytest (backend/tests/, excluding acceptance/)
2. DB migrations       → uv run --package database python -m database.migrate
3. Docker build & push → builds from repo root, pushes to Fly.io registry
4. Deploy              → flyctl deploy (image pinned by run_number + short SHA)
5. Smoke test          → GET /ready with retry (6 attempts × 10-second delay)
6. Acceptance tests    → pytest backend/tests/acceptance/ against the live URL
```

A failure at steps 1–4 leaves the previous deployment active. Steps 5–6 run after deploy; a smoke test failure will surface but the deploy has already happened — investigate immediately.

**To trigger manually:** `workflow_dispatch` on `deploy-backend.yml` from the GitHub Actions UI.

---

## Docker Image

- **Registry:** Fly.io private container registry
- **Image tag format:** `{run_number}-{short_sha}` (e.g. `42-a1b2c3d`)
- **`latest` tag:** also pushed on every deploy
- **Build context:** repository root (required for uv workspace resolution)
- **Dockerfile:** `backend/Dockerfile` — two-stage build; runtime stage runs as non-root `appuser`

---

## Rollback

To roll back to a previous version:

```bash
flyctl deploy --image registry.fly.io/<app-name>:<previous-tag> --config backend/fly.toml
```

Find previous tags in the GitHub Actions run history (each run logs the image tag) or in the Fly.io registry. The `app-name` is managed by the team and not published here.

Alternatively, re-run the GitHub Actions workflow from a previous commit using the `workflow_dispatch` trigger with that commit checked out.

---

## Operational Commands

These commands require the Fly CLI (`flyctl`) and a valid `FLY_API_TOKEN`. The app name is stored in the team's private runbook.

```bash
# Stream live logs
flyctl logs -a <app-name>

# Open an interactive shell on the running machine
flyctl ssh console -a <app-name>

# List deployed machines and their status
flyctl status -a <app-name>

# List image tags in the registry
flyctl releases -a <app-name>

# Add or rotate a secret (restarts the machine)
flyctl secrets set KEY=value -a <app-name>

# Remove a secret
flyctl secrets unset KEY -a <app-name>
```

---

## Configuration

All runtime configuration is stored as Fly.io secrets. No secret or credential should ever be committed to source control or added to this documentation.

For the full list of environment variables, their types, and default values, see:

- `backend/.env.example` in the repository — all variables with descriptions
- [Infrastructure Requirements TRD](../technical-requirements/trd-infrastructure-requirements.md) — required variables checklist and per-component tables

**Variable categories (all stored as Fly.io secrets):**

| Category | Examples of what is stored |
| --- | --- |
| LLM provider | API key, model name, stream timeout, token budget |
| RAG / embeddings | API key, relevance threshold, top-K, table name |
| Database | Connection string with SSL |
| Slack handoff | Webhook URL, bot token |
| Email fallback | SMTP host, credentials, recipient address |
| Business hours | Timezone (IANA), start/end hour, same-day cutoff |
| CORS | Allowed origin (the host website domain) |
| LLM observability | Langfuse public key, secret key, host |

After rotating a secret, the machine restarts automatically. Verify recovery via `GET /ready`.

---

## Load Testing

Load tests verify the backend meets the Time to First Token (TTFT) performance requirement under realistic concurrent load. This is a **manual Phase 5 DoD gate** — not triggered automatically.

**Tool:** k6 (Grafana), script at `backend/tests/load/load-test.js`

**Thresholds:**

| Metric | Threshold |
| --- | --- |
| p95 TTFT | < 3,000 ms |
| Error rate | < 5% |

TTFT is measured as TTFB (`http_req_waiting`) — the time from request sent to first byte received. For a streaming SSE endpoint this equals time-to-first-token and is the standard k6 proxy.

**Test configuration:**

- 10 virtual users (VUs), 2-minute ramp-up → 10-minute sustained → 30-second ramp-down
- Each VU simulates 5–7 conversation turns with 15–30 second think-time between turns (realistic cadence)
- Message mix: 60% RAG-triggering queries, 40% non-RAG queries
- Machine is pre-warmed to 1 instance before the test run to prevent cold-start latency from contaminating TTFT measurements

**How to run:**

1. Go to the repository's **Actions** tab.
2. Select the **`load-test.yml`** workflow.
3. Click **Run workflow** and provide the `base_url` input (the API base URL to test against).
4. The workflow pre-warms the machine, runs the k6 test, and uploads a `results.json` artifact (30-day retention).

k6 exits with code 1 if any threshold fails, which fails the workflow job.

**If the test fails:**

- Review the k6 step output for which threshold failed and the actual p95/error-rate values.
- If `p95 TTFT` exceeds 3,000 ms under 10 VUs: scale the machine — set `min_machines_running = 1` and `max_machines_running = 2` in `backend/fly.toml`. No code changes required. See ADR-006 for the full scaling criteria.
