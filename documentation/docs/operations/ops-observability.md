---
description: "Operations runbook for Growth Chat monitoring — application logs, LLM tracing, health checks, cost monitoring, and alerting."
---

# Observability

The system uses two observability layers: **application logs** for infrastructure and request-level events, and **LLM tracing** for AI-specific signals (token usage, retrieval quality, qualification outcomes).

---

## Application Logs

Logs are emitted as structured JSON by the `shared/telemetry` package. The service is tagged as `growth-chat-api` in all log entries.

The log destination (log aggregation provider) is configured via environment variables — see ADR-008 for the provider decision and `backend/.env.example` for the relevant variable names.

**What is logged:**

- Request lifecycle (session start, message received, response dispatched)
- Qualification state changes
- Handoff dispatch attempts and outcomes
- RAG retrieval results (chunk count, whether threshold was met)
- Rate limit events (429 responses)
- Backend startup and shutdown
- Analytics provider failures (degraded, not fatal)

**What is NOT logged (PII protection):**

- Message content from visitors
- Visitor name or email in log body (only in the handoff subsystem's structured fields, which go to the database)
- Raw API responses

Log retention is 30 days, managed by the log provider.

---

## LLM Tracing (Langfuse)

LLM calls, RAG retrievals, and embedding spans are traced via Langfuse (see ADR-007). Tracing activates only when Langfuse credentials are present in the environment. If credentials are absent, the analytics provider silently uses a no-op implementation — the chat continues normally but no traces are recorded.

**Trace structure per chat request:**

```text
Trace (session_id)
  └── Span: chat_request
        ├── Generation: LLM call (model, input messages, token counts, latency)
        ├── Retriever span: retrieve_knowledge (query, chunks returned, scores)  [if RAG triggered]
        └── Embedding span: embed query (model, input text)  [if RAG triggered]
```

**Events to monitor in Langfuse:**

| Event | Significance |
| --- | --- |
| `qualification_state_changed` | Visitor progressed through qualification stages |
| `handoff_dispatched` | A lead was sent to Slack and CRM |
| `handoff_partial_failure` | One channel (Slack or CRM) failed after retries |
| `handoff_total_failure` | Both channels failed — email fallback triggered |
| `rag_retrieved` | RAG returned chunks above the relevance threshold |
| `rag_no_result` | RAG found no chunks above threshold for a query |
| `session_expired` | Session closed due to inactivity TTL |

**Langfuse is hosted on the EU cloud instance** for GDPR data residency compliance (all compute in Frankfurt).

---

## Health Monitoring

Two endpoints are available for external health checks:

| Endpoint | Use | Normal state |
| --- | --- | --- |
| `GET /health` | Process liveness (Docker HEALTHCHECK) | 200 `{"status": "ok"}` always, if the process is up |
| `GET /ready` | Application readiness (Fly.io HTTP check) | 200 `{"status": "ready"}` when the app has finished starting; 503 during startup or shutdown |

**Fly.io polling:** `/ready` is checked every 30 seconds, 5-second timeout, 30-second grace on start. Three consecutive failures trigger a machine restart.

**Interpreting `/ready` 503:**

- At startup: normal — wait for the grace period to pass.
- After a successful deploy: transient — clears once the database connection pool is established.
- Persistent 503 post-deploy: startup failure — check `flyctl logs` for errors (common causes: missing required secret, database connection failure, Langfuse client failure).

---

## Cost Monitoring

The system has a configurable monthly LLM cost ceiling (default: $50/month). This is **not enforced at the application level** — it is a soft cap that feeds the alerting system.

Monitor in Langfuse:

- **Token consumption per session** — outlier sessions may indicate prompt injection or abuse.
- **Total daily token spend** — compare against the monthly budget to project overage risk.
- **`rag_retrieved` call rate** — a spike may indicate over-triggering of RAG, which increases cost.

The per-session token budget (default: 16,000 cumulative tokens) is enforced at the application level. Sessions that exceed the budget receive a graceful closure and cannot continue.

---

## Alerting

The following alerts should be configured in the log provider and/or Fly.io:

| Alert | Source | Trigger condition |
| --- | --- | --- |
| Backup job failure | Fly.io machine exit event | Backup machine exits with non-zero code — **configure once the backup job is implemented** |
| Persistent readiness failure | Fly.io health check | `/ready` returns 503 for >3 consecutive checks |
| Monthly LLM spend threshold | Langfuse / log provider | Spend exceeds 80% of `MONTHLY_COST_CAP_USD` |
| Rate limit spike | Application logs | 429 response rate exceeds baseline |
| Total handoff failure | Application logs / Langfuse | `handoff_total_failure` event emitted |

Specific alert configuration (thresholds, notification channels, escalation paths) is maintained in the team's private runbook.
