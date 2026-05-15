---
description: "TRD Section 8 — Security Requirements for the AI-powered lead qualification chat — TLS, authentication, PII handling, rate limiting, GDPR compliance, and secret management."
---

# Security Requirements

> **Relationship to other TRD sections:**
>
> - Section 4 (Data Models) defines PII classification, scrubbing rules, and retention policy — this section enforces them at the transport and application layers.
> - Section 5 (API Specifications) references this section for rate limiting values and authentication enforcement.
> - Section 6 (Infrastructure Requirements) references this section for CORS configuration, Cloudflare Rules, and secret management.
> - Engineering concerns EC-08 and EC-12 are resolved in this section.

---

## Transport Security

| Requirement | Specification |
| --- | --- |
| Encryption in transit | TLS 1.3 minimum. TLS 1.0 and 1.1 are disabled. |
| TLS termination point | Cloudflare terminates TLS at the edge before traffic reaches the Fly Machine. The Fly internal network between Cloudflare and the Fly Machine uses Cloudflare's origin certificate (Flexible or Full (Strict)). |
| Certificate management | Cloudflare-managed certificates. No self-signed certificates in staging or production. |
| HSTS | Enforced via Cloudflare with `max-age=31536000; includeSubDomains`. |
| Encryption at rest | Neon Postgres encrypts data at rest using AES-256. This covers all `SessionState`, `HandoffRecord`, and `KnowledgeChunk` data. Tigris backup storage is AES-256 encrypted at rest. |

---

## Authentication and Authorisation

### Widget-to-API Authentication

The chat widget authenticates to the Chat API using a static per-deployment key.

| Requirement | Specification |
| --- | --- |
| Mechanism | Static API key passed in the `ZGC-API-KEY` request header on every `POST /chat` request (Section 5). |
| Key scope | One key per deployment environment (development, staging, production). Keys are independent and rotated independently. |
| Key storage | Stored as a Fly.io secret (`ZGC_API_KEY`). Never committed to source control. Never compiled into the widget bundle. |
| Key validation | Validated synchronously before the request reaches the orchestrator. An absent or invalid key returns `401 INVALID_API_KEY` (Section 5). |
| Rotation | Keys must be rotatable without a code deployment — rotation requires only updating the Fly secret and the widget CDN bundle's build variable. The key has no expiry baked in; rotation is triggered on suspected compromise or scheduled quarterly. |

### Authorisation Model

The system has no multi-user authorisation model. All authenticated widget requests are treated as anonymous visitor sessions. There is no authenticated visitor identity — visitors are identified only by their `session_id` (a client-generated UUID v4), which is pseudonymous and not linked to any user account.

Internal services (Neon, Slack, CRM, SMTP) authenticate using their own credentials (see Section 6.4). No internal service is exposed publicly.

---

## PII Handling

PII classification and field-level definitions are the authoritative responsibility of Section 4. This section specifies the enforcement rules at the transport and application layers.

### PII Fields in Scope

| Field | Location | Treatment |
| --- | --- | --- |
| `visitor_email` | `SessionState`, `HandoffRecord` | Scrubbed before Anthropic API calls; excluded from application logs; deleted on 90-day retention expiry |
| `visitor_name` | `SessionState`, `ContextPacket` | Same treatment as `visitor_email` |
| `signals_observed[].evidence` | `SessionState` | PII-adjacent (may contain raw visitor phrases); subject to 90-day retention; not logged separately |

### Scrubbing Before LLM API Calls

Before any `SessionState` content is included in a prompt sent to the Anthropic API or the OpenAI Embeddings API:

- `SessionState.visitor_email` → replaced with `"[email redacted]"`
- `SessionState.visitor_name` → replaced with `"[name redacted]"`

Scrubbing is applied unconditionally — even if the fields are `None` — to prevent accidental transmission if defaults change. This is implemented as a single `scrub_pii()` function called in the `generate_response` node before prompt assembly (Section 3).

### No PII in Application Logs

The Chat API logs only: `session_id`, request timestamp, HTTP status code, and response latency. The `message` body is never logged. PII fields are never written to raw application logs.

### GDPR Data Notice

The chat widget displays a data processing notice on the visitor's first interaction, before any visitor data is transmitted to the backend. The notice copy is set via `VITE_GDPR_NOTICE_TEXT` (Section 6) and must be reviewed by legal before production deployment.

The `zgc:gdpr_acknowledged` analytics event is fired when the visitor dismisses the notice (Section 3 — Analytics Events).

---

## Rate Limiting

Rate limiting is implemented at two layers: the network edge (Cloudflare) and the application layer (`slowapi` middleware in FastAPI). Both layers are required — neither alone covers all attack vectors (ADR-006).

### Per-IP Rate Limiting — Cloudflare Edge (EC-12)

| Parameter | Value |
| --- | --- |
| Limit | 30 requests per 10 minutes per visitor IP |
| Enforcement point | Cloudflare Rules, before traffic reaches the Fly Machine |
| Client IP source | `CF-Connecting-IP` header (see Section 6 — Client IP Resolution) |
| Response on breach | Cloudflare returns `429` before the request reaches the API |
| Scope | Applies to all requests to `POST /chat` |

The Cloudflare Rule threshold (30 req / 10 min) is intentionally generous relative to normal conversation pace (typically 1–3 messages per minute). It targets volumetric abuse, not conversation depth.

### Per-Session Rate Limiting — Application Layer

| Parameter | Value |
| --- | --- |
| Limit | 20 messages per session per 5 minutes |
| Enforcement point | `slowapi` middleware in FastAPI, keyed by `ZGC-Session-ID` header |
| Response on breach | `429 RATE_LIMITED` with `retry_after_seconds: 30` (Section 5 — HTTP Error Responses) |
| Scope | Applies per `session_id` regardless of source IP |

Per-session limiting is applied at the application layer because session context (`session_id`) is only available after the `ZGC-API-KEY` has been validated.

### Per-Session Token Budget (EC-12)

| Parameter | Value |
| --- | --- |
| Limit | `MAX_TOKENS_PER_SESSION` (default: `16000` cumulative input + output tokens) |
| Enforcement point | Conversation Orchestrator — tracked from Anthropic API usage metadata per turn |
| Behaviour on breach | Orchestrator returns a graceful session-limit message and marks the session `termination_type = token_limit_reached`; no new turns are accepted |

The token budget enforces per-session cost control independently of the rate limiter. A session may hit the token budget before the message rate limit if turns are long.

### Cost Alerting

| Parameter | Value |
| --- | --- |
| Monthly cost cap | `MONTHLY_COST_CAP_USD` (default: `$50`) |
| Enforcement | Soft cap — not enforced at the application layer. Consumed by the observability layer (Section 9) to configure spend alerting at 80% of threshold. |
| Action on breach | Alert sent to the engineering team. No automatic request blocking. |

---

## Bot and Abuse Prevention

| Layer | Mechanism | Scope |
| --- | --- | --- |
| Cloudflare Bot Score | Blocks requests from known automated traffic (crawlers, scrapers) based on Cloudflare's free-tier Bot Score. | Network edge — before any API compute is consumed. |
| `ZGC-API-KEY` validation | Requests without a valid key are rejected with `401` before reaching the orchestrator. | Application layer. |
| `message` size limit | Messages exceeding 2,000 characters are rejected with `400 INVALID_MESSAGE` (Section 5). | Application layer. |
| CORS restriction | Only the configured `ALLOWED_ORIGIN` is permitted. Wildcard origins (`*`) are prohibited in staging and production (Section 6). | Application layer. |

**Limitation:** Cloudflare free-tier Bot Score does not include OWASP managed rule groups or sophisticated bot fingerprinting. If volumetric bot abuse emerges in production, upgrading to Cloudflare Pro ($20/month) or migrating to AWS WAF is the documented remediation path (ADR-006).

---

## Secret Management

All credentials and keys are stored as Fly.io Secrets (`fly secrets set`). They are injected as environment variables at runtime and are never:

- Committed to source control
- Printed in application logs
- Included in the widget bundle (`chat.js`)
- Returned in API responses

The full secret inventory is defined in Section 6 (Environment Variables). Secrets are grouped by component: LLM, embeddings, persistence, handoff, and widget build.

Secret rotation procedure: update the Fly secret via `fly secrets set`, then restart the Fly Machine. No code deployment is required. Rotation must be performed for all secrets on suspected compromise. Scheduled rotation cadence is quarterly for `ZGC_API_KEY`; other secrets are rotated on change of personnel or vendor.

---

## 8.7 GDPR Compliance (EC-08)

### Legal Basis

The system processes personal data (visitor email, name, and conversation content) under the legitimate interest of the data controller for business development purposes. The `VITE_GDPR_NOTICE_TEXT` displayed on first interaction must accurately describe this basis. The notice copy must be approved by legal before production deployment.

### Data Retention

Retention rules are defined in Section 4 (Data Models) and are summarised here for reference:

| Data type | Retention period | Deletion mechanism |
| --- | --- | --- |
| `SessionState` (including conversation history) | 90 days from session end | Scheduled deletion job (backup cron machine) |
| `HandoffRecord` | 1 year (PII fields scrubbed at 90 days) | Scheduled deletion job |
| `KnowledgeChunk` | Indefinite (no visitor PII) | Manual deletion via indexing pipeline `--delete` flag |
| Application logs | 30 days | Log rotation policy (Fly.io log drain or equivalent) |

### EU Data Residency

All runtime components are Frankfurt-based:

- Chat API: Fly.io `fra` (Frankfurt)
- PostgreSQL (session state, knowledge index): Neon `eu-central-1` (Frankfurt)
- LLM processing: Anthropic EU data processing endpoint (ADR-001)
- Embeddings: OpenAI EU endpoint (`OPENAI_EU_ENDPOINT`, ADR-003)

No personal data leaves EU territory at any step of the processing chain. This satisfies GDPR Article 44 (transfers to third countries) without relying on Standard Contractual Clauses for the primary processing path.

### Data Processing Agreements

| Processor | DPA status | Requirement |
| --- | --- | --- |
| Anthropic (LLM) | Enterprise DPA available; EU data processing addendum required | Required for production traffic with real visitor data only. |
| OpenAI (Embeddings) | DPA available; EU data processing addendum required | Required for production traffic with real visitor data only. |
| Cloudflare | DPA available (Cloudflare Customer DPA) | Required for production traffic with real visitor data only. |
| Neon | DPA available | Required for production traffic with real visitor data only. |
| Fly.io | DPA available | Required for production traffic with real visitor data only. |

**EC-08 resolution (updated):** This project is an AI engineering study. The system will only process synthetic test data — no real visitor data will be handled in any deployment phase of this project. DPA execution is therefore not required for any build or staging phase. If the system is extended to handle real visitor traffic in a future commercial deployment, DPA sign-off with all five processors becomes a go/no-go condition before opening to production traffic. That decision must be tracked separately at that time.

Engineering may proceed through all phases — including staging deployment — without DPAs in place.

### Subject Rights

The system stores visitor data in `SessionState` and `HandoffRecord` under `session_id`. Because `session_id` is a client-generated UUID with no login, the system has no mechanism to look up data by visitor identity without the `session_id`. The data controller must establish a procedure for responding to Subject Access Requests and Right to Erasure requests that accounts for this. This procedure is outside the scope of this TRD but must be documented before production launch.

---

## Engineering Concerns Resolved by This Section

| EC | Concern | Resolution |
| --- | --- | --- |
| EC-08 | GDPR Data Processing Agreement with LLM provider — hard blocker for production | §8.7: DPA status for all five processors defined; production launch blocked until all DPAs are executed; EU data residency confirmed at every processing step |
| EC-12 | Missing rate limiting, cost controls, and abuse prevention | §8.4: Per-IP rate limiting via Cloudflare Rules (30 req / 10 min); per-session rate limiting via `slowapi` (20 msg / 5 min); per-session token budget via `MAX_TOKENS_PER_SESSION`; monthly cost alerting via `MONTHLY_COST_CAP_USD` |

---

*This section is part of the authoritative TRD. Any change to the security architecture described here requires a corresponding ADR (if it affects a technology decision) and a version increment to this document.*
