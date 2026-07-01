---
description: "Infrastructure, LLM API, and operating cost breakdown for the Growth Chat MVP — 90-day baseline and scaling projection."
---

# Cost Report — Website Growth Chat (MVP)

**Date:** July 2026
**Scope:** Infrastructure, third-party API, and operating costs for the first 90 days (MVP validation), with a scaling projection.
**Source:** Project ADRs 001, 003, 006, 007, 008 and the TRD.

---

## 1. Traffic assumptions (observed baseline)

| Parameter | Value |
| --- | --- |
| Unique site visitors/day | ~100 |
| Chat activation rate | ~5% |
| Chat sessions/day (estimated) | ~5 |
| Chat sessions/month (estimated) | ~150 |
| Turns per conversation (average) | 6–8 |
| % of turns triggering RAG (`retrieve_knowledge`) | ~60% |

This baseline corresponds to a "corporate website" traffic profile with no significant spikes. Expected production concurrency is below 1 simultaneous session.

---

## 2. Estimated monthly cost breakdown

| Component | Provider | Estimated MVP cost (~150 conv./month) | Notes |
| --- | --- | --- | --- |
| Chat API compute | Fly.io (`fra`, Frankfurt) | ~$2 | `shared-cpu-1x, 256MB`, with autoscale-to-zero |
| PostgreSQL database (pgvector + session state) | Neon (`eu-central-1`) | $0–5 | Free tier covers <500 knowledge chunks; scales with usage |
| CDN / Edge / Rate limiting / WAF | Cloudflare | $0 | Free tier: rate limiting rules, Bot Score, CDN |
| **Cloud infrastructure subtotal** | | **$2–10** | Reference figure from ADR-006 |
| LLM — response generation and qualification | Anthropic API (Claude Haiku 4.5) | ~$1–2 | See detailed calculation below |
| RAG query embeddings | OpenAI (`text-embedding-3-small`) | ~$0.02 | Estimated in ADR-003: 10,000 query embeddings/month ≈ 100 tokens each |
| LLM observability (traces, tokens, evaluation) | Langfuse Cloud (EU) | $0 | Free tier: 50,000 observations/month — sufficient for the full MVP period |
| Application logging + uptime monitoring | Better Stack | $0 | Free tier: 3-day log retention; uptime monitor included |
| **AI services and observability subtotal** | | **~$1–2** | |
| **TOTAL ESTIMATED MONTHLY COST (MVP)** | | **~$3–12/month** | |

---

## 3. LLM cost calculation (detail)

- **Model:** Claude Haiku 4.5 — $0.25 / 1M input tokens, $1.25 / 1M output tokens.
- **Average context per turn:** 4,000–10,000 tokens (system prompt + history + RAG + current turn), per the budget defined in the TRD.
- **Estimate at MVP volume:**
  - 150 conversations/month × ~6 turns = ~900 turns/month
  - Input: 900 turns × ~5,000 tokens ≈ 4.5M tokens → **~$1.1/month**
  - Output: 900 turns × ~400 tokens ≈ 360K tokens → **~$0.45/month**
  - **Total LLM ≈ $1.5–2/month** at MVP volume

This figure is well below the configured soft cost ceiling (`MONTHLY_COST_CAP_USD = $50`) and the architecture review threshold defined in ADR-001 ($500/month, at which point prompt caching or model routing would be evaluated).

---

## 4. Costs not included in the recurring calculation (contingent)

| Item | Trigger condition | Estimated cost |
| --- | --- | --- |
| Better Stack — paid plan | If log volume exceeds 3GB/month or retention >3 days is needed | from $29/month |
| Langfuse — paid plan | If 50,000 observations/month are exceeded | Flat rate (no per-seat pricing); confirm at Langfuse.com |
| Neon — paid plan | If the knowledge corpus grows beyond the free tier (>0.5GB) | Variable, scales with usage |
| Prompt caching / model routing | If LLM cost sustainably exceeds $500/month | Reduces cached-token cost by ~80% |
| Migration to AWS Fargate + RDS + WAF | If enterprise-grade infrastructure is required post-validation | ~$60–90/month (ADR-006 reference) |
| DPA / legal compliance (Anthropic, OpenAI, Better Stack, Langfuse, Cloudflare) | Before processing real visitor data in production | Not quantified — legal/administrative cost, not infrastructure |

---

## 5. Comparison: discarded alternative (reference)

For context, the infrastructure alternative evaluated and discarded (AWS Fargate + RDS `db.t3.micro` + ALB + WAF) had an entry cost of **$60–90/month**, versus **$2–10/month** for the chosen stack (Fly.io + Neon + Cloudflare). The decision prioritizes cost minimization and operational simplicity for a 1–2 engineer team during the MVP validation phase (ADR-006).

---

## 6. Executive summary

| Scenario | Estimated monthly cost |
| --- | --- |
| **Current MVP (~150 conv./month)** | **~$3–12/month** |
| With paid logging/observability (if free tier is exceeded) | +$29–50/month |
| Scaling to 10x volume with no architecture changes | ~$15–40/month (LLM cost scales linearly; cloud infra has ample headroom) |
| Migration to enterprise infrastructure (AWS) | ~$60–90/month for compute/database alone |

**Conclusion:** MVP operating cost is marginal (single-digit to low double-digit dollars per month), thanks to the combination of free tiers (Cloudflare, Langfuse, Better Stack, Neon) and a low-cost LLM model (Claude Haiku 4.5). The largest cost-deviation risk is conversation volume, not per-token unit price — any significant traffic scaling should trigger a revalidation of these figures.

---

*Note: all figures are drawn from estimates documented in the project's ADRs (001, 003, 006, 007, 008) and the TRD. They do not substitute for real production spend monitoring (Langfuse + Anthropic API alerts + Better Stack).*
