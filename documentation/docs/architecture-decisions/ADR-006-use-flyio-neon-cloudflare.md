---
description: "ADR-006: Decision to use Fly.io (fra, Frankfurt) for the Chat API runtime, Neon (eu-central-1, Frankfurt) for PostgreSQL, and Cloudflare (free tier) as the DNS proxy for rate limiting and bot protection — covers alternatives considered (AWS Fargate, AWS App Runner, Azure, Render, Railway, Fly Postgres), rationale for minimal operational surface on a small team with a cost-minimisation priority, and constraints on future decisions."
---

# ADR-006 — Use Fly.io, Neon, and Cloudflare for the MVP Infrastructure

**Status:** Accepted
**Date:** 2026-05-11
**Decision owner:** Engineering Lead
**Participants:** Engineering Lead, AI Engineering Lead

---

## Context

The website chat system requires a cloud hosting environment for three
runtime components: the Chat API (FastAPI, streaming SSE), the PostgreSQL
instance (pgvector extension for knowledge retrieval + langgraph-checkpoint-postgres
for session state), and the CDN for the static chat widget bundle (`chat.js`).
An offline indexing pipeline also runs periodically but is not a latency-sensitive
workload.

The project is greenfield — no existing cloud infrastructure constrains the
choice. The team operating the MVP is small (1–2 engineers), has AWS experience,
and has set cost minimisation as the primary selection criterion. Visitor traffic
is primarily EU-based, making EU data residency relevant for GDPR compliance,
though it is not a hard architectural constraint given that DPAs with external
providers (Anthropic, OpenAI) handle the LLM and embedding API surfaces
separately (EC-08, ADR-001, ADR-003).

The ADR sequencing note in the Engineering Review specifies that ADR-001 (LLM
provider) must be resolved before this decision, as the cloud provider and LLM
provider choices are partially coupled. ADR-001 selected the Anthropic API
directly — not via a managed cloud AI service such as Amazon Bedrock or Azure
OpenAI. This decouples the cloud provider decision from the LLM provider: any
cloud platform is equally capable of making outbound HTTPS calls to
`api.anthropic.com` and `api.openai.com`.

The PostgreSQL backend serves two distinct roles in this system: pgvector for
knowledge retrieval (ADR-003) and `langgraph-checkpoint-postgres` for session
state (ADR-004). The reliability and operational characteristics of this instance
are therefore a primary concern — it is not a peripheral service.

The system is a publicly accessible chat widget, which requires per-IP rate
limiting, basic bot protection, and cost controls before production (EC-12,
TRD Section 8). These controls must be implemented at the network edge — before
traffic reaches the API container — to be effective against volumetric abuse.
The choice of how to implement edge security is therefore part of the
infrastructure decision.

---

## Decision

**We will use Fly.io (`fra`, Frankfurt) for the Chat API runtime, Neon
(`eu-central-1`, Frankfurt) for PostgreSQL, and Cloudflare (free tier) as
the DNS proxy for TLS termination, per-IP rate limiting, and basic bot
protection.**

Specific services used:

- **Fly Machines** — containerised Chat API (FastAPI) with autoscale-to-zero
  between traffic spikes
- **Neon Serverless Postgres** — fully managed PostgreSQL with pgvector extension
  and `langgraph-checkpoint-postgres` tables, provisioned in `eu-central-1`;
  PITR and database branching included on all plans
- **Cloudflare (free tier)** — DNS proxy in front of the Fly Machine's public
  hostname; provides TLS termination, per-IP rate limiting via Cloudflare Rules,
  and basic Bot Score filtering at the network edge; replaces Tigris as the
  CDN origin for `chat.js` (Cloudflare Pages or Cloudflare CDN serves the
  static widget bundle)
- **Tigris Object Storage** (Fly-native, S3-compatible) — origin store for
  `chat.js`; Cloudflare caches and serves it at the edge

---

## Alternatives Considered

| Option | Description | Why considered | Why not chosen |
| --- | --- | --- | --- |
| **Fly.io + Neon + Cloudflare — Chosen** | Fly Machines for the API runtime; Neon serverless Postgres; Cloudflare free tier as DNS proxy for rate limiting, bot protection, TLS, and CDN. | Lowest operational overhead; Neon resolves the reliability gap of Fly Postgres; Cloudflare resolves EC-12 at zero cost and zero infrastructure | — Chosen |
| Fly.io + Neon (no Cloudflare) | Same stack without a network edge layer. | Simpler — fewer accounts. | EC-12 requires per-IP rate limiting before traffic reaches the API. Without an edge layer, rate limiting must live entirely in the application (`slowapi`), which is effective per-session but cannot stop volumetric IP-based abuse before it consumes API compute. Cloudflare free tier costs nothing and adds the missing edge layer. |
| Fly.io + Fly Postgres | Same API runtime, but Postgres hosted on Fly as a managed container. Single billing account. | Simplest single-vendor setup. | No PITR, no automated failover, no managed minor version upgrades. An unrecoverable failure means losing both the knowledge index and session state simultaneously. Neon eliminates this risk at comparable cost. |
| AWS Fargate + WAF (eu-west-1) | ECS/Fargate for API, RDS for Postgres, ALB + AWS WAF for rate limiting and bot protection. Team has prior AWS experience. | AWS WAF provides native rate limiting and bot protection that directly resolves EC-12 without a separate proxy. Team familiarity reduces onboarding risk. | WAF integration is the strongest argument for AWS, but Fargate requires 1–2 days of setup (VPC, IAM roles, security groups, ALB, task definitions) that delivers no product value in a 90-day MVP. Cloudflare free tier resolves EC-12 with 30 minutes of DNS configuration. Cost at MVP scale: Fargate + RDS + ALB starts at ~$60–80/month; Fly + Neon + Cloudflare is ~$5–15/month. At MVP horizon, the cost and setup difference is not justified. AWS Fargate is the natural migration target if the MVP validates and the system needs enterprise-grade infrastructure. |
| AWS App Runner + WAF | Managed container runtime on AWS, lower ops overhead than Fargate, native WAF integration. | Simpler than Fargate; WAF still available; team AWS experience applies. | App Runner has a documented 60-second response timeout limitation that affects long-lived SSE connections. The chat widget uses streaming token delivery that can run 10–30 seconds per response — App Runner's timeout behaviour on SSE is a production risk. Fargate does not have this constraint. App Runner is therefore unsuitable for this use case regardless of other merits. |
| Azure (westeurope) | Azure Container Apps for API, Azure Database for PostgreSQL, Azure Front Door for WAF/CDN. | GDPR compliance strength; Azure OpenAI would integrate cleanly if Claude were accessed via Azure. | Azure OpenAI integration advantage does not apply — ADR-001 uses the Anthropic API directly. Pricing structure similar to AWS — minimum charges independent of traffic. No existing team familiarity. |
| Render | Managed PaaS, EU regions, predictable per-service pricing. | Simpler than AWS; good DX. | Free tier spins down after 15 minutes of inactivity with 30–60 second cold starts — unacceptable for a streaming SSE chat. Always-on starts at $7/service/month with per-seat workspace fees on top. No native rate limiting or WAF. |
| Railway | Usage-based PaaS on own hardware, EU-West (Amsterdam) region. | Comparable simplicity to Fly.io; usage-based pricing scales to near-zero. | Recurring outage pattern in the EU-West region in 2025, including a December 2025 incident that paused builds across all tiers. For a lead qualification system where downtime means lost leads, this reliability record is disqualifying at MVP. No native rate limiting or WAF. |

---

## Rationale

The selection criteria applied in order of priority are: cost minimisation,
operational simplicity for a small team, EU data residency, and path to v2
scaling.

**Splitting API runtime and database across two services.** The decision to
use Fly.io for the API and Neon for Postgres — rather than Fly.io for both — is
driven by a specific reliability gap in Fly Postgres. Fly Postgres is a managed
container running the official Postgres Docker image. It lacks point-in-time
recovery, automated failover, and managed minor version upgrades. Given that
the Postgres instance serves both the knowledge index (pgvector) and the session
state checkpointer (ADR-004), an unrecoverable database failure means losing
both simultaneously. Neon is a purpose-built managed Postgres service with PITR,
branching, and automatic failover on all plans — at a comparable or lower cost.
The operational cost of a second service is one connection string and one
additional account. The reliability improvement justifies it.

**Cost at MVP scale.** Fly Machines for the Chat API cost approximately
$1.94/month at continuous operation on `shared-cpu-1x, 256MB`, scaling to
near-zero with autoscale-to-zero enabled. Neon's free tier covers 0.5 GB
storage and on-demand compute — the MVP knowledge base (estimated <500 chunks
at ~512 tokens each) fits within this limit. At moderate traffic, Neon costs
approximately $0–5/month. Cloudflare's free tier covers rate limiting rules,
basic Bot Score filtering, and CDN delivery at no cost. Total estimated MVP
infrastructure: **$2–10/month**. The AWS Fargate equivalent (Fargate + RDS
`db.t3.micro` + ALB + WAF) starts at approximately $65–90/month.

**Operational simplicity.** Fly.io requires no VPC, IAM, ALB, or security group
configuration. A complete `fly.toml` for the Chat API is under 40 lines; `flyctl`
handles deployment, secrets, scaling, and logs. Neon requires only a connection
string — no instance configuration, no extension installation commands beyond
`CREATE EXTENSION vector`, no vacuum scheduling. For a 1-2 engineer team, the
combined operational surface of Fly + Neon is significantly lower than any AWS
stack.

**EU data residency.** Fly.io `fra` (Frankfurt) hosts the Chat API. Neon
`eu-central-1` (Frankfurt) hosts the Postgres instance. Combined with the
Anthropic EU data processing commitment (ADR-001, EC-08) and the OpenAI EU
endpoint (ADR-003), all personal data processed by the system remains within
EU boundaries at every step.

**Database branching for staging.** Neon's branching feature allows a staging
environment to branch from the production database snapshot — providing
production-equivalent data for integration testing without a separate instance
or a manual dump/restore. This is a material benefit for the Phase 5 testing
workstream (70–80 structured test conversations against the production knowledge
base).

**Cloudflare as the edge security layer (EC-12).** The system is a publicly
accessible widget, which requires per-IP rate limiting and basic bot protection
before traffic reaches the API container. Putting Cloudflare as a DNS proxy in
front of the Fly Machine's public hostname provides this at the network edge —
before any LLM API cost is incurred. Cloudflare's free tier supports custom
rate limiting rules (e.g. 30 requests per 10 minutes per IP) and a basic Bot
Score that blocks known crawlers and scrapers. This resolves the IP-level
component of EC-12 with 30 minutes of DNS configuration and zero ongoing cost.
Per-session rate limiting and token budget enforcement remain in the application
layer (`slowapi` middleware in FastAPI), where session context is available.
The combination covers all four EC-12 requirements without a dedicated gateway
service. Cloudflare also serves as the CDN layer for the `chat.js` widget
bundle, with Tigris as the origin store — consolidating TLS, rate limiting, bot
protection, and CDN delivery under one free-tier account.

**Why not AWS Fargate + WAF despite team AWS experience.** AWS WAF is the
strongest available solution for EC-12 — native rate limiting, managed bot
rules, and WAF in a single integrated service. It is the natural long-term
choice. However, Fargate requires 1–2 days of VPC, IAM, ALB, and task
definition setup that delivers no product value during the 90-day MVP
validation period. Cloudflare free tier resolves the same EC-12 requirements
in 30 minutes. AWS App Runner was also evaluated but has a documented SSE
timeout limitation incompatible with the streaming chat use case. AWS Fargate
is explicitly identified as the migration target if the MVP validates and
enterprise-grade infrastructure becomes justified.

---

## Consequences

### Positive

- Estimated MVP infrastructure cost $2–10/month — well below the $65–90/month
  AWS Fargate + WAF equivalent
- Cloudflare free tier provides per-IP rate limiting, basic bot protection, TLS
  termination, and CDN delivery — resolving the IP-level component of EC-12
  with zero cost and ~30 minutes of DNS configuration
- Neon provides PITR, automatic failover, and managed upgrades — resolving the
  primary reliability gap of Fly Postgres
- Neon branching enables production-equivalent staging environments without a
  separate database instance
- Zero VPC, IAM, ALB, or security group configuration; full API deployment via
  `fly.toml` and `flyctl`
- Both `fra` and `eu-central-1` are Frankfurt-based — all runtime components
  within EU territory for GDPR Article 44 compliance
- pgvector available on Neon via `CREATE EXTENSION vector` with no custom Docker
  image required
- Autoscale-to-zero for both Fly Machines and Neon compute at off-peak hours
- AWS Fargate is an explicit documented migration path if the MVP validates —
  the application code has no Fly.io dependencies

### Negative / Trade-offs

- **Three accounts instead of one.** Fly.io, Neon, and Cloudflare are separate
  services. Operational cost is low — one connection string, one `fly secret
  set`, one DNS change — but onboarding requires three account setups.
- **Cloudflare free tier bot protection is basic.** Cloudflare's free Bot Score
  blocks known automated traffic but does not provide the managed rule groups
  (OWASP, known bad actors) available in Cloudflare Pro ($20/month) or AWS WAF
  Bot Control. For MVP traffic volumes this is acceptable. If sophisticated
  bot abuse emerges in production, upgrading to Cloudflare Pro or migrating to
  AWS WAF is the remediation path.
- **Network latency between Fly `fra` and Neon `eu-central-1`.** Both are
  Frankfurt-based; round-trip latency is expected to be 5–15ms per operation.
  At the current access pattern — one checkpointer read and one write per turn —
  this adds 10–30ms per turn, well within the 3s TTFT budget. If Phase 5 load
  testing shows otherwise, Neon supports AWS PrivateLink, but that requires
  moving the API runtime to AWS.
- **Cloudflare sits between the visitor and Fly.io.** Visitor IPs seen by the
  Fly Machine are Cloudflare proxy IPs unless `CF-Connecting-IP` header
  forwarding is configured. The FastAPI application must read
  `CF-Connecting-IP` (not `X-Forwarded-For`) for per-IP rate limiting in
  `slowapi` to work correctly at the session layer.

### Constraints on future decisions

- `CHECKPOINT_DB_URL` must point to the Neon connection string, stored as a Fly
  secret (`fly secrets set DATABASE_URL=...`). In v1, both the pgvector and
  checkpointer roles use the same Neon database and connection string.
- The Chat API Dockerfile must install `tzdata` explicitly — Fly's default Python
  base images (Debian slim) do not include it, causing `zoneinfo` to fail at
  runtime (TRD Section 3.5, Business Hours Detection Module).
- The Chat API must read the `CF-Connecting-IP` header (set by Cloudflare) as
  the authoritative client IP for per-session rate limiting in `slowapi`. Using
  `X-Forwarded-For` or the socket IP will return Cloudflare proxy IPs and break
  IP-based rate limiting.
- CORS configuration on the Chat API must explicitly allow the host site's origin.
  Cloudflare proxies the API domain; the CORS origin is the host site, not
  Cloudflare.
- Cloudflare Rate Limiting rules must be configured for the `/chat` endpoint
  specifically — not as a global site rule — to avoid throttling CDN asset
  delivery for `chat.js`.
- If traffic grows to require multiple API Machine replicas, the Neon
  checkpointer handles concurrent access safely. `MemorySaver` must not be used
  in any multi-replica deployment (ADR-004).
- **Migration path to AWS Fargate:** the application container, environment
  variables, and Neon connection string are fully portable. Migration requires
  VPC setup, ALB configuration, ECS task definition, and AWS WAF rule
  replication of the Cloudflare rules — estimated 1–2 days. No application code
  changes are required.

---

## Compliance Notes

- The Chat API runs in Fly.io `fra` (Frankfurt, Germany). The Postgres instance
  runs in Neon `eu-central-1` (Frankfurt, Germany). Both are within EU territory
  for GDPR Article 44 transfer restriction purposes.
- Cloudflare acts as a DNS proxy and processes visitor IP addresses and HTTP
  headers. IP addresses constitute personal data under GDPR Article 4. Cloudflare
  offers a Data Processing Addendum covering its proxy services — this must be
  reviewed and signed before the proxy handles production traffic. Cloudflare
  DPA: cloudflare.com/cloudflare-customer-dpa.
- Tigris Object Storage serves the static `chat.js` widget bundle. The widget
  contains no personal data. EU data residency requirements apply to the Chat
  API and Postgres only.
- A Data Processing Agreement with Fly.io must be reviewed and signed before
  personal data is processed in production. Fly.io DPA: fly.io/legal/privacy-policy.
- A Data Processing Agreement with Neon must be reviewed and signed before
  personal data is stored in production. Neon DPA: neon.tech/legal.
- All three DPAs (Fly.io, Neon, Cloudflare) are parallel legal tasks, consistent
  with the pattern established in EC-08 for Anthropic and ADR-003 for OpenAI.

---

## Review Triggers

This decision should be revisited if:

- Monthly infrastructure cost on Fly.io + Neon exceeds $100 USD — at that point
  the cost differential with AWS Fargate narrows and the broader AWS ecosystem
  becomes more competitive.
- Sophisticated bot abuse emerges in production that Cloudflare's free Bot Score
  cannot mitigate — upgrade to Cloudflare Pro ($20/month) before evaluating
  platform migration.
- Neon `eu-central-1` experiences more than one unplanned availability event in
  any 30-day production period.
- Latency between Fly `fra` and Neon `eu-central-1` exceeds 30ms p95 under
  production load — at that point, Neon PrivateLink via AWS should be evaluated,
  which implies migrating the API runtime to AWS Fargate.
- The MVP validates the hypothesis and the system enters a growth phase — AWS
  Fargate + WAF is the identified migration target and should be planned at that
  point.
- The team grows to include a dedicated DevOps engineer, reducing the weight of
  the operational simplicity criterion.
- Any of Fly.io, Neon, or Cloudflare changes its EU data residency guarantees
  or DPA terms.

---

## References

- [PRD § 7.1 — Cloud Provider candidates and evaluation criteria](../../product-requirements/#product-requirements-document-prd-7-technical-constraints-and-candidates-71-stack-candidates-v1-cloud-provider)
- [Engineering Review — ADR sequencing note](../../product-requirements/engineering-review#engineering-review-ai-powered-lead-qualification-chat-technical-stack-analysis) — ADR-001 must precede ADR-006
- [Engineering Review § EC-12 — Rate limiting, cost controls, and abuse prevention](../../product-requirements/engineering-review#engineering-review-ai-powered-lead-qualification-chat-engineering-concerns-ec-12-missing-rate-limiting-cost-controls-and-abuse-prevention) — resolved by Cloudflare Rules + `slowapi`
- [ADR-001 — Use Anthropic Claude Haiku 4.5 as the LLM Provider](./ADR-001-llm-provider.md) — direct Anthropic API; decouples cloud provider from LLM provider
- [ADR-002 — Use LangGraph for Conversation Orchestration](./ADR-002-conversation-orchestrator.md) — checkpointer requires external KV store compatible with `BaseCheckpointSaver`
- [ADR-003 — Use pgvector and OpenAI Embeddings for Knowledge Retrieval](./ADR-003-use-pgvector-and-openai-embeddings-for-knowledge-retrieval.md) — pgvector on the Neon Postgres instance
- [ADR-004 — Use MemorySaver for development and PostgreSQL checkpointer for production](./ADR-004-use-memorysaver-and-postgres-for-state-persistence.md) — Neon as the production checkpointer backend
- [Engineering Review § EC-08 — GDPR DPA requirement](../../product-requirements/engineering-review#engineering-review-ai-powered-lead-qualification-chat-engineering-concerns-ec-08-gdpr-data-processing-agreement-with-llm-provider)
- [Fly.io pricing](https://fly.io/docs/about/pricing)
- [Fly.io Tigris documentation](https://fly.io/docs/reference/tigris)
- [Neon pricing](https://neon.tech/pricing)
- [Neon pgvector documentation](https://neon.tech/docs/extensions/pgvector)
- [Neon branching](https://neon.tech/docs/introduction/branching)
- [Cloudflare Rate Limiting](https://developers.cloudflare.com/waf/rate-limiting-rules)
- [Cloudflare Bot Score](https://developers.cloudflare.com/bots/concepts/bot-score)
- [Cloudflare DPA](https://www.cloudflare.com/cloudflare-customer-dpa)

---

*ADRs are immutable once accepted. If this decision is superseded, create a new ADR and update the Status field above to `Superseded by ADR-NNN`. Do not edit the body of this document.*
