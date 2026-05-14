---
description: "ADR-008: Decision to use Better Stack (Logtail + Uptime) as the application logging and uptime monitoring platform — covers Fly.io log shipping, structured error logging, backup failure alerting, and uptime monitoring for the 99.5% availability target."
---

# ADR-008 — Use Better Stack for Application Logging and Uptime Monitoring

**Status:** Accepted
**Date:** 2026-05-14
**Decision owner:** Engineering Lead
**Participants:** Engineering Lead, AI Engineering Lead

---

## Context

The website chat system requires application-level observability covering two
distinct needs: structured log retention for diagnosing infrastructure and
system errors, and uptime monitoring to track the 99.5% availability target
defined in the PRD (NFR 6.2).

LLM-layer observability — traces, prompt inputs/outputs, token usage, node
latency, RAG retrieval outcomes — is addressed by ADR-007 (Langfuse). This
ADR covers the complementary layer: system errors, infrastructure failures,
and availability monitoring that Langfuse does not capture.

The specific events requiring application-level logging are defined in TRD
Section 9.1 and include: `checkpointer_write_failure`, `embedding_api_failure`,
`vector_search_failure`, `llm_generation_failure`, `stream_timeout`,
`backup_failed`, and rate limit hits. Of these, `backup_failed` is explicitly
called out in TRD Section 6 (Infrastructure Requirements) as requiring routing
to "the observability layer (Section 9)" — it is not catchable from within the
application itself, as the backup runs as a separate Fly Machine.

The Chat API runs on Fly.io (`fra`, Frankfurt). Fly.io emits all container
`stdout/stderr` output as a native log stream and supports external log
shipping via a Vector-based log shipper or direct HTTP ingestion. This means
application logs require no code changes to the FastAPI application — only
a log destination configuration.

The observability platform must satisfy EU data residency (GDPR Article 44),
consistent with the constraint applied to every other component in this stack.

---

## Decision

**We will use Better Stack (Logtail for log management, Uptime for availability
monitoring) as the application logging and uptime monitoring platform for the
website chat MVP.**

Better Stack covers two roles:

1. **Structured log management** — Fly.io application logs shipped to Logtail
   via the native Fly log shipper integration. Includes structured search,
   retention, and alert rules for the error events defined in TRD Section 9.
2. **Uptime monitoring** — HTTP monitor on the `/health` endpoint of the Chat
   API, with Slack alert on downtime, tracking the PRD 99.5% availability
   target. Heartbeat monitor on the backup cron Machine exit to surface
   `backup_failed` events (TRD Section 6).

---

## Alternatives Considered

| Option | Description | Why considered | Why not chosen |
| --- | --- | --- | --- |
| **Better Stack — Chosen** | Hosted log management (Logtail) + uptime monitoring in a single platform. Native Fly.io integration via official documentation. Free tier: 3GB logs/3-day retention, 10 monitors, Slack + email alerts. EU data residency available. | Lowest setup cost for the Fly.io stack. Covers both logging and uptime in one account. Free tier sufficient for MVP. | — Chosen |
| Grafana Cloud (free tier) | Logs (Loki) + metrics (Prometheus/Mimir) + dashboards + alerts. Free tier: 50GB logs/month, 10k active metrics. EU region (Frankfurt) available. | More powerful for application metrics — counters, gauges, histograms, and custom dashboards. Natural migration path if TRD Section 9 metrics require dedicated instrumentation. | No native Fly.io integration — requires configuring a Vector or Alloy agent as a container sidecar, adding setup and maintenance overhead. For MVP, the additional capability does not justify the setup cost. Documented as the migration path if application metrics become a requirement post-MVP. |
| Fly.io native logs only | `stdout/stderr` retained by Fly.io for 7 days, accessible via `flyctl logs` or the Fly dashboard. Zero configuration. | Already available with no setup. Covers basic debugging during development. | No alerting, no structured search beyond basic text filtering, 7-day retention only. Cannot implement the `backup_failed` alert required by TRD Section 6, as Fly Machine exit events are not surfaced as searchable log entries without an external destination. Insufficient for production. |

---

## Rationale

The selection follows the same criteria applied in ADR-006: minimum cost,
minimum operational overhead, and EU data residency.

**Integration with Fly.io.** Better Stack is one of the officially documented
Fly.io log shipping destinations with a dedicated integration guide. The
integration requires creating a Fly log shipper app and setting two secrets
(`BETTER_STACK_SOURCE_TOKEN`, `BETTER_STACK_HOSTNAME`) — no changes to the
Chat API application code and no sidecar containers. This is the lowest
possible integration overhead for the chosen runtime.

**Free tier coverage.** The free tier provides 3GB logs per month with 3-day
retention, 10 uptime monitors, and Slack + email alerts. At MVP conversation
volumes, application error logs will be well under 1GB/month. The 10 monitor
slots cover the two required monitors (Chat API `/health` endpoint and backup
cron heartbeat) with capacity for additional monitors without upgrading.
The 3-day retention is sufficient for active incident diagnosis; Langfuse
retains the LLM trace history for richer post-incident analysis.

**Uptime monitoring and `backup_failed` alerting.** Better Stack's heartbeat
monitor resolves the `backup_failed` alerting requirement from TRD Section 6.
The backup cron Machine sends an HTTP ping to a Better Stack heartbeat URL on
successful completion. If the ping is not received within the expected window
(daily at 02:00 CET + 30-minute grace), Better Stack fires a Slack alert. This
is the lowest-overhead implementation of the requirement — no custom alerting
infrastructure, no changes to the backup script beyond adding a single `curl`
call.

**Grafana Cloud trade-off.** Grafana Cloud's free tier is more capable for
application metrics (custom counters and histograms for TTFT, error rates by
component). However, the Fly.io integration requires a Vector or Alloy agent
running as a sidecar — additional container configuration and ongoing version
maintenance. For MVP, where the primary need is error visibility and uptime
alerting rather than metric dashboards, this overhead is not justified. Grafana
Cloud is the documented migration path if TRD Section 9 metrics require a
dedicated instrumentation layer post-MVP.

---

## Consequences

### Positive

- Fly.io log shipping configured in under 30 minutes — no application code
  changes, no sidecar containers.
- `backup_failed` alerting requirement from TRD Section 6 resolved via
  Better Stack heartbeat monitor — no custom alerting infrastructure required.
- Uptime monitoring with Slack alerts covers the PRD 99.5% availability target
  with a documented SLA check mechanism.
- Free tier sufficient for the full 90-day MVP validation period — zero
  additional cost.
- Structured log search enables filtering by `session_id`, error type, and
  component — sufficient for diagnosing the error events defined in TRD
  Section 9.1.
- Single platform for logs and uptime monitoring — one account, one alert
  destination configuration.

### Negative / Trade-offs

- **3-day log retention on free tier.** Incidents not investigated within
  3 days of occurrence lose their raw log context. Mitigation: Langfuse retains
  LLM traces for longer; for infrastructure errors specifically, the 3-day
  window covers the active response period. If longer retention is required,
  the paid plan starts at $29/month with configurable retention.
- **No application metrics on free tier.** Better Stack's free tier covers logs
  and uptime monitors but not custom metric instrumentation (counters,
  histograms). The TRD Section 9 metrics (TTFT p95, error rates by component)
  cannot be implemented as dedicated time-series metrics without upgrading or
  switching to Grafana Cloud. For MVP, these metrics are approximated from
  structured log fields.
- **Third-party data processor.** Application logs may contain `session_id`
  and error context that constitutes personal data under GDPR Article 4. A
  Data Processing Addendum with Better Stack must be executed before production
  logs contain data derived from real visitor sessions — consistent with the
  DPA pattern across all ADRs.
- **Log shipper as an additional Fly app.** The Fly log shipper runs as a
  separate Fly Machine that consumes the log stream. It adds one additional
  `fly.toml` to the repository and one additional deployment to manage. Operational
  surface is low but not zero.

### Constraints on future decisions

- Application logs must be structured JSON emitted to `stdout` by the FastAPI
  application. Unstructured log lines are searchable in Logtail but cannot be
  filtered by field. The logging configuration for FastAPI must emit JSON with
  at minimum: `timestamp`, `level`, `event`, `session_id` (when available),
  and `component`.
- The backup cron Machine script must send an HTTP ping to the Better Stack
  heartbeat URL on successful exit. The heartbeat URL is stored as a Fly secret
  (`BETTERSTACK_HEARTBEAT_URL`). If the ping call fails, the backup is still
  considered complete — the observability call must not block the backup.
- If TRD Section 9 application metrics (TTFT p95, per-component error rates)
  are required as dedicated time-series instrumentation post-MVP, Grafana Cloud
  is the identified migration path. Migration requires adding a Vector or Alloy
  sidecar to the Chat API container — no changes to the FastAPI application
  itself if structured JSON logging is already in place.
- PII scrubbing applies to application logs as it does to LLM traces. Visitor
  email addresses and names must not appear in raw log output. `session_id`
  is the safe identifier for log correlation; PII fields must be excluded from
  log statements.

---

## Compliance Notes

- Better Stack offers EU data residency for log storage. EU region must be
  selected when creating the Logtail source — data must not be stored in the
  US region. EU data residency satisfies GDPR Article 44 transfer restrictions
  applied consistently across this stack.
- Application logs may contain `session_id` and IP addresses that constitute
  personal data under GDPR Article 4. A Data Processing Addendum (DPA) with
  Better Stack must be reviewed and signed before production logs contain
  data derived from real visitor sessions. Better Stack DPA available at
  betterstack.com/security.
- The DPA is a parallel legal task, consistent with the pattern established
  for Anthropic (ADR-001), OpenAI (ADR-003), Cloudflare, Fly.io, Neon
  (ADR-006), and Langfuse (ADR-007).
- IP addresses logged by the application (e.g. for rate limit events) are
  processed by Cloudflare before reaching the Chat API. The application logs
  the `CF-Connecting-IP` value, which is the real visitor IP. This is personal
  data under GDPR and must be covered by the Better Stack DPA.

---

## Review Triggers

This decision should be revisited if:

- Better Stack changes its EU data residency guarantees or DPA terms.
- Log volume consistently exceeds 3GB/month and 3-day retention proves
  insufficient for incident diagnosis — upgrade to the paid plan ($29/month)
  or migrate to Grafana Cloud.
- TRD Section 9 application metrics require dedicated time-series
  instrumentation — Grafana Cloud is the identified migration path.
- The Fly.io log shipper integration introduces version maintenance burden
  that outweighs the setup simplicity advantage.

---

## References

- [ADR-006 — Use Fly.io, Neon, and Cloudflare](./ADR-006-use-flyio-neon-cloudflare.md) — Fly.io as the runtime; log shipper runs as a Fly Machine
- [ADR-007 — Use Langfuse Cloud as the LLM Observability Platform](./ADR-007-use-langfuse-for-llm-observability.md) — complementary LLM-layer observability; scope boundary between the two ADRs
- [TRD Section 6 — Infrastructure Requirements](../technical-requirements/index.md#technical-requirements-document-6-infrastructure-requirements) — `backup_failed` alert requirement; Fly Machine exit event routing
- [TRD Section 9 — Logging](../technical-requirements/index.md#technical-requirements-document-9-observability) — error events requiring structured log capture
- [TRD Section 9 — Metrics](../technical-requirements/index.md#technical-requirements-document-9-observability) — application metrics deferred to post-MVP
- [PRD § 6.2 — Availability](../product-requirements-document.md#product-requirements-document-prd-6-non-functional-requirements-62-availability) — 99.5% monthly uptime target
- [PRD § 6.4 — Observability](../product-requirements-document.md#product-requirements-document-prd-6-non-functional-requirements-64-observability) — error logging requirements
- [Better Stack Fly.io integration documentation](https://betterstack.com/docs/logs/fly-io/)
- [Better Stack pricing](https://betterstack.com/pricing)
- [Better Stack security and DPA](https://betterstack.com/security)

---

*ADRs are immutable once accepted. If this decision is superseded, create a new ADR and update the Status field above to `Superseded by ADR-NNN`. Do not edit the body of this document.*
