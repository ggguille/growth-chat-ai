---
description: "TRD Section 9 — Structured JSON logging contracts (event table, PII rules), Better Stack metric queries and uptime monitors, and the full analytics event schema for frontend CustomEvents and backend Langfuse traces — satisfies PRD NFR 6.4."
---

# Observability

## Logging

Application logs are emitted as structured JSON to `stdout` by the FastAPI application and shipped to Better Stack (Logtail) via the Fly.io log shipper (ADR-008). Retention is 3 days on the Better Stack free tier.

### Log Format

Every log line must be a single JSON object. The following fields are mandatory on every entry:

| Field | Type | Description |
| --- | --- | --- |
| `timestamp` | string (ISO 8601 UTC) | Time of the event — `datetime.now(UTC).isoformat()` |
| `level` | `"INFO"` \| `"WARN"` \| `"ERROR"` | Severity |
| `event` | string | Machine-readable event name (snake_case, values defined below) |
| `session_id` | string (UUID v4) \| `null` | Present for all session-scoped events; `null` for infrastructure events with no session context |
| `component` | string | Originating component (values: `orchestrator`, `rag`, `handoff`, `api`, `backup`) |

Additional fields are event-specific and defined in the event table below. No field outside this specification may contain PII — visitor email addresses and names must not appear in any log line (TRD Section 8).

### Event Table

| Event | Level | Component | Additional fields | Description |
| --- | --- | --- | --- | --- |
| `state_extraction_failure` | WARN | `orchestrator` | `turn_index: int`, `error: str` | `update_state` LLM call failed or timed out; session continues with stale state |
| `llm_generation_failure` | ERROR | `orchestrator` | `turn_index: int`, `error: str` | `generate_response` LLM call failed; fallback message returned, routed to `propose_handoff` |
| `stream_timeout` | ERROR | `orchestrator` | `turn_index: int`, `timeout_ms: int` | First token not received within `LLM_STREAM_TIMEOUT_MS`; same recovery as `llm_generation_failure` |
| `checkpointer_write_failure` | ERROR | `orchestrator` | `turn_index: int`, `error: str` | State write to PostgreSQL failed; session continues with stale persisted state; current turn's qualification progress may be lost |
| `embedding_api_failure` | WARN | `rag` | `turn_index: int`, `error: str` | OpenAI embedding API call failed or timed out; response proceeds without retrieved context |
| `vector_search_failure` | ERROR | `rag` | `turn_index: int`, `error: str` | pgvector query failed (DB connection error); response proceeds without retrieved context; sustained failures require DB connectivity alert |
| `corrupt_chunk_skipped` | WARN | `rag` | `chunk_id: str`, `turn_index: int` | Retrieved chunk was empty or unparseable; excluded from results; document should be re-indexed |
| `rag_extra_tool_call_ignored` | WARN | `rag` | `turn_index: int`, `call_count: int` | LLM issued more than `MAX_TOOL_CALLS_PER_TURN` retrieve calls; additional calls ignored |
| `handoff_channel_failure` | ERROR | `handoff` | `channel: "slack"\|"crm"`, `attempt: int`, `http_status: int \| null`, `error: str` | Individual delivery attempt failed; logged per retry attempt |
| `handoff_partial_failure` | ERROR | `handoff` | `failed_channel: "slack"\|"crm"`, `fallback_sent: bool` | One channel exhausted retries; fallback email dispatched if `fallback_sent: true` |
| `handoff_total_failure` | ERROR | `handoff` | `fallback_sent: bool` | Both channels exhausted retries; fallback email dispatched if `fallback_sent: true` |
| `rate_limit_hit` | WARN | `api` | `limit_type: "ip"\|"session"\|"token_budget"`, `ip_hash: str \| null` | Rate limit or token budget exceeded; `ip_hash` is a one-way hash of `CF-Connecting-IP` — not the raw IP |
| `backup_failed` | ERROR | `backup` | `error: str` | Daily backup Fly Machine did not send a heartbeat ping to Better Stack within the expected window (surfaced via Better Stack heartbeat monitor, not emitted by the application directly — see Metrics section) |
| `session_corrupted` | ERROR | `orchestrator` | `error: str` | Checkpointer read returned an unresolvable state; widget reloads session with a new `session_id` |
| `prompt_compliance_violation` | WARN | `orchestrator` | `turn_index: int` | LLM generated a Stage 3 proposal outside the `propose_handoff` node; detected by response validator |
| `fallback_activated` | WARN | `api` | `reason: "http_error"\|"stream_timeout"\|"connection_error"` | Widget entered fallback state; pre-stream HTTP error (503 or 401) triggered fallback |

### PII and Log Safety

- `session_id` is safe to log — it is a UUID with no visitor-identifying information.
- `ip_hash` in `rate_limit_hit` must be a one-way SHA-256 hash of the raw IP, not the IP itself.
- Visitor email, name, company, and role must never appear in any log field, including `error` strings. If an error message from an external API includes PII, it must be stripped before logging.
- Log lines are shipped to Better Stack EU (Frankfurt) under the Better Stack DPA (ADR-008).

---

## Metrics

No dedicated time-series metrics instrumentation is implemented in MVP. The metrics defined in this section are implemented as structured log queries in Better Stack (Logtail), using the JSON fields defined in Logging section.

This approach is sufficient for the MVP validation period. If post-MVP operational requirements demand dedicated time-series instrumentation (custom histograms, p95 latency dashboards, cost tracking), Grafana Cloud is the identified migration path — see ADR-008 Review Triggers.

### Better Stack Log Queries

The following queries must be saved as named views in the Better Stack workspace before the system goes to production. Each query is a Better Stack SQL-like filter over structured log fields.

| Metric | Query definition | Purpose | Alert |
| --- | --- | --- | --- |
| LLM error rate | `event IN ("llm_generation_failure", "stream_timeout")` — count per hour | Detect degraded LLM service | Alert if count > 5 in any 1-hour window |
| Checkpointer failure rate | `event = "checkpointer_write_failure"` — count per hour | Detect DB write degradation | Alert if count > 3 in any 1-hour window |
| RAG failure rate | `event IN ("embedding_api_failure", "vector_search_failure")` — count per hour | Detect OpenAI or pgvector degradation | Alert if count > 5 in any 1-hour window |
| Handoff failure rate | `event IN ("handoff_partial_failure", "handoff_total_failure")` — count per day | Track lead delivery reliability | Alert if count > 2 in any 24-hour window |
| Rate limit hit frequency | `event = "rate_limit_hit"` — count per 10 minutes per `limit_type` | Detect volumetric abuse or budget overrun | Alert if `token_budget` hits > 0 in any 1-hour window |
| Fallback activation rate | `event = "fallback_activated"` — count per hour | Detect systemic API unavailability | Alert if count > 3 in any 1-hour window |
| Prompt compliance violations | `event = "prompt_compliance_violation"` — count per day | Track prompt adherence; trigger prompt engineering review | Alert if count > 5 in any 24-hour window |

### Uptime Monitoring

Uptime monitoring is implemented in Better Stack Uptime (ADR-008), not as application-layer metrics.

| Monitor | Type | Target | Check interval | Alert channel | SLA target |
| --- | --- | --- | --- | --- | --- |
| Chat API health | HTTP | `GET /health` → 200 | 1 minute | Slack `#alerts` | 99.5% monthly (PRD NFR 6.2) |
| Backup cron heartbeat | Heartbeat | Ping expected daily at 02:00 CET ± 30 min | — | Slack `#alerts` | Daily — missed ping = `backup_failed` |

### Monthly Cost Alert

The monthly LLM cost cap (`MONTHLY_COST_CAP_USD`, default `$50`) is a soft cap enforced via a Better Stack alert, not at the application layer (TRD Section 8). The alert fires at 80% of the configured threshold.

Cost data is not available directly in Better Stack. For MVP, cost monitoring is manual — the engineering team checks Anthropic usage dashboard weekly. A dedicated cost alert is a post-MVP instrumentation task.

---

## Analytics Events

Analytics events are fired at two layers: the frontend widget (client-side) and the backend orchestrator (server-side). The two layers are complementary — they do not duplicate each other. The canonical event schema is defined here; the component-level implementations in `trd-component-specifications` (widget) and `trd-api-specification` (`emit_event`) reference this section.

**LLM analytics destination:** Backend events are emitted to Langfuse (ADR-007) via `emit_event`. Langfuse receives them as structured trace metadata.

**Frontend analytics destination:** Frontend events are dispatched as `CustomEvent` on the `<growth-chat>` element. The host page is responsible for forwarding them to whatever analytics platform the client uses. The widget has no direct dependency on any analytics SDK. The specific platform used by the client is outside the scope of this system.

**PII rule:** No visitor PII appears in any analytics event field. `session_id` is the only visitor-correlated identifier permitted in events.

---

### Frontend Events (widget → host page CustomEvent)

Fired by the chat widget and dispatched on the `<growth-chat>` element. The host page listens and forwards to its analytics platform.

| Event name | Trigger | `detail` fields |
| --- | --- | --- |
| `zgc:chat_opened` | Visitor opens the chat panel | `session_id: string`, `timestamp: string (ISO 8601)` |
| `zgc:first_message_sent` | Visitor sends their first message in a session | `session_id: string`, `timestamp: string` |
| `zgc:qualification_state_changed` | Backend `done` event signals a `lead_level` change from previous value | `session_id: string`, `lead_level: "hot"\|"warm"\|"cold"`, `timestamp: string` |
| `zgc:contact_captured` | Visitor provides their email in the chat | `session_id: string`, `timestamp: string` *(email is not included — PII stays server-side)* |
| `zgc:escalation_triggered` | Backend `done` event has `stage3_proposal_issued: true` | `session_id: string`, `handoff_reason: string`, `lead_level: string`, `timestamp: string` |
| `zgc:conversation_ended` | Explicit close, 15-min inactivity, or session expiry | `session_id: string`, `termination_type: "explicit_close"\|"inactivity_timeout"\|"session_expiry"`, `turn_count: number`, `timestamp: string` |
| `zgc:fallback_activated` | Widget enters fallback state (pre-stream HTTP error) | `session_id: string`, `reason: "connection_error"\|"http_error"\|"stream_timeout"`, `timestamp: string` |
| `zgc:gdpr_acknowledged` | Visitor dismisses the GDPR data notice | `session_id: string`, `timestamp: string` |

---

### Backend Events (orchestrator → Langfuse via `emit_event`)

Fired server-side by the `write_state` node at the end of each turn, or by the Human Handoff Subsystem on handoff dispatch.

| Event name | Trigger | Fields |
| --- | --- | --- |
| `qualification_state_changed` | A `QualificationState` dimension changed level on this turn | `session_id: string`, `dimension: string`, `from_level: string`, `to_level: string`, `signal_type: string`, `turn_index: int`, `timestamp: string` |
| `handoff_dispatched` | `dispatch_handoff` called by `propose_handoff` node | `session_id: string`, `handoff_reason: string`, `lead_level: string`, `business_hours: bool`, `timestamp: string` |
| `handoff_delivered` | Both Slack and CRM confirmed delivery | `session_id: string`, `slack_ok: bool`, `crm_ok: bool`, `timestamp: string` |
| `handoff_partial_failure` | One channel failed after exhausting retries | `session_id: string`, `failed_channel: "slack"\|"crm"`, `timestamp: string` |
| `handoff_total_failure` | Both channels failed after exhausting retries | `session_id: string`, `timestamp: string` |
| `rag_retrieved` | `retrieve_knowledge` returned results above threshold | `session_id: string`, `query_length: int`, `chunks_returned: int`, `top_score: float`, `turn_index: int`, `timestamp: string` |
| `rag_no_result` | `retrieve_knowledge` returned no results above threshold | `session_id: string`, `turn_index: int`, `timestamp: string` |
| `prompt_compliance_violation` | LLM generated a Stage 3 proposal outside `propose_handoff` | `session_id: string`, `turn_index: int`, `timestamp: string` |

---

### Frontend / Backend Event Mapping

Some session lifecycle events have both a frontend and a backend representation. These are complementary, not duplicates: the frontend event reflects the visitor action; the backend event reflects the state change computed server-side.

| Frontend event | Corresponding backend event | Relationship |
| --- | --- | --- |
| `zgc:qualification_state_changed` | `qualification_state_changed` | Frontend fires on `lead_level` change from `done` event; backend fires on any `QualificationState` dimension change (more granular — includes dimension and signal type) |
| `zgc:escalation_triggered` | `handoff_dispatched` | Frontend fires on `stage3_proposal_issued: true` in `done` event; backend fires when `dispatch_handoff` is actually called — same turn, complementary data |
| `zgc:fallback_activated` | *(none — infrastructure event)* | Frontend-only; logged as `fallback_activated` in application logs |
| `zgc:conversation_ended` | *(none — session lifecycle, tracked via SessionState)* | Frontend-only; session closure is implicit in the absence of further turns |

---

*This section satisfies PRD NFR 6.4 (analytics event schema with field names and types specified before implementation). Engineering concerns resolved: none directly — this section implements the observability layer referenced by EC-05, EC-08, EC-09, EC-12, and EC-13 resolutions elsewhere in the TRD.*
