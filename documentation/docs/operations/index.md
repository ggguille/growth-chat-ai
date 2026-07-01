---
description: "Production operations reference for the Growth Chat system — component inventory, CI/CD map, and external dependencies."
---

# Operations Overview

Growth Chat is an AI-powered lead qualification chat widget deployed on behalf of a consulting company. It qualifies inbound website visitors, answers questions about company services, and routes hot prospects to the sales team in real time. The system is designed for low operational overhead: most components deploy automatically on code push and scale to zero when idle.

This section is written for system administrators and operators who are responsible for keeping the application running in production. For design intent, architecture decisions, and functional requirements see the rest of the documentation.

---

## Component Inventory

| Component | Platform | Technology | Deployed by |
| --- | --- | --- | --- |
| [Backend API](./ops-backend.md) | Fly.io (Frankfurt) | FastAPI + LangGraph, Python 3.14, Docker | `deploy-backend.yml` |
| [Frontend Widget](./ops-frontend.md) | Object storage CDN | Vite IIFE bundle, React 18, TypeScript | `deploy-frontend.yml` |
| [PostgreSQL Database](./ops-database.md) | Neon Serverless (Frankfurt) | PostgreSQL 17 + pgvector | Schema managed by `deploy-backend.yml` (migrations step) |
| [Documentation Site](./ops-documentation.md) | GitHub Pages | DocMD static site, Node | `deploy-documentation.yml` |
| [Knowledge Ingestion](./ops-ingestion.md) | One-off command / CI | Python (uv), OpenAI embeddings | Manual via `ingest-knowledge.yml` or local CLI |

---

## CI/CD Pipeline Map

All deployments run through GitHub Actions and target the `production` environment. No deployment should be performed manually outside of the procedures described in each component runbook.

| Workflow file | Component | Auto-trigger | Manual trigger |
| --- | --- | --- | --- |
| `deploy-backend.yml` | Backend API + DB migrations | Push to `main` touching `backend/**`, `shared/**`, `data/**`, or lock files | `workflow_dispatch` |
| `deploy-frontend.yml` | Frontend widget | Push to `main` touching `frontend/**` | `workflow_dispatch` |
| `deploy-documentation.yml` | Documentation site | Push to `main` touching `documentation/**` | `workflow_dispatch` |
| `ingest-knowledge.yml` | Knowledge base ingestion | None (manual only) | `workflow_dispatch` |
| `e2e.yml` | End-to-end browser tests | None (manual only) | `workflow_dispatch` (optional test filter input) |
| `eval-behaviour.yml` | DeepEval behaviour test suite | After `Deploy Backend` completes on `main`; or PR touching `evaluation/**` | `workflow_dispatch` |
| `eval-rag.yml` | RAGAS RAG quality pipeline | After `Ingest Knowledge Base` completes on `main` | `workflow_dispatch` |
| `eval-redteam.yml` | Promptfoo adversarial red team | After `Deploy Backend` completes on `main`; or PR touching `evaluation/**` | `workflow_dispatch` |
| `load-test.yml` | Load testing | None (manual only) | `workflow_dispatch` (requires `base_url` input) |

**Backend deploy pipeline order (sequential, each step gates the next):**

```text
Unit tests → DB migrations → Docker build & push → Deploy to Fly.io → Smoke test → Acceptance tests
```

A migration failure blocks the deploy before any new code ships — the previous deployment stays active. A smoke test failure means the new version is already live; there is no automatic rollback. If the smoke test fails, manually roll back using the procedure in the [Backend API runbook](./ops-backend.md).

---

## External Service Dependencies

The system has runtime dependencies on the following external services. A prolonged outage of any of them degrades or disables the corresponding capability.

| Service | Purpose | Failure impact |
| --- | --- | --- |
| Anthropic API | LLM inference (Claude Haiku) | Chat becomes unavailable; widget shows fallback |
| OpenAI API | Text embedding for RAG queries | Knowledge retrieval disabled; chat continues without context |
| Neon PostgreSQL | Session state, vector index, handoff records, CRM | Full service outage |
| Object storage CDN | Widget bundle delivery | Widget fails to load; visitors see static page |
| Slack API | Human handoff notification to `#new-leads` | Handoff notification fails; email fallback activates |
| SMTP provider | Dual-channel failure fallback email | No notification on total handoff failure |
| Langfuse | LLM observability and tracing | Monitoring blind; chat continues normally |
| Application log provider | Structured log ingestion | Log visibility lost; chat continues normally |

---

## Component Runbooks

- [Backend API](./ops-backend.md) — deploy, rollback, health checks, logs, configuration
- [Frontend Widget](./ops-frontend.md) — deploy, CDN cache, failure modes, configuration
- [Database](./ops-database.md) — migrations, backup, recovery, data retention
- [Knowledge Ingestion](./ops-ingestion.md) — when and how to re-run the ingestion pipeline
- [Observability](./ops-observability.md) — logs, LLM tracing, health monitoring, alerting
- [Documentation Site](./ops-documentation.md) — deploy, local preview, adding content
