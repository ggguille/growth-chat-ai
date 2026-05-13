---
description: "TRD Section 7 — Performance Requirements: TTFT and retrieval latency targets, per-stage latency budget, and stress test plan for the AI-powered lead qualification chat."
---

# Performance Requirements

## Targets

| Metric | Target | Percentile | Measurement point |
| --- | --- | --- | --- |
| Chat response TTFT (Time to First Token) | < 3s | p95 | From API request received at Chat API to first SSE token delivered to client |
| RAG retrieval latency (embedding + vector search + threshold filter) | < 500ms | p95 | From `retrieve_knowledge` tool call received to `RetrievalResult` returned |
| OpenAI embedding API call | < 200ms | p95 | From HTTP request sent to response received; EU endpoint required |
| HNSW vector search (pgvector) | < 100ms | p95 | SQL query execution time; valid for corpus < 10K vectors — re-evaluate if corpus exceeds 1M |
| Widget load time | < 1s | — | Non-blocking; `defer` load strategy; bundle must not block host page critical path |
| Widget bundle size | ≤ 200KB gzipped | — | Measured at Phase 1 build; if > 250KB gzipped, evaluate tree-shaking before considering alternative library |

**Streaming requirement:** Streaming must be enabled in the frontend widget from day one. The TTFT target is not achievable without streaming — full-response latency is not the target metric and is not measured (EC-09).

---

## Latency Budget

The following breakdown is informative. The per-stage figures are not binding SLAs, but they validate that the 3s end-to-end TTFT target is achievable and provide a baseline for diagnosing regressions.

| Stage | Typical range | p95 budget |
| --- | --- | --- |
| Embedding query (OpenAI EU endpoint) | 50–100ms | 200ms |
| HNSW vector search (pgvector) | 50–100ms | 100ms |
| Threshold filter + result assembly | < 10ms | 20ms |
| LLM first token (Anthropic, streaming enabled) | 500ms–2,000ms | ~2,500ms |
| Network round-trip (EU, CDN) | 50–150ms | 180ms |
| **Total** | **700ms–2,500ms** | **< 3,000ms** |

The 500ms p95 retrieval target (embedding + vector search + filter) is derived from this budget. With retrieval completing within 500ms, the remaining ~2.5s is sufficient for LLM first-token delivery under normal operating conditions.

Turns that do not trigger a `retrieve_knowledge` call skip the embedding and vector search stages entirely, making the full ~2.8s available to the LLM.

---

## Stress Test Plan

**Observed traffic baseline:** ~100 unique visitors per day, ~5 per hour, with no significant traffic spikes (corporate website profile).

**Expected concurrent sessions in production:** At a 5% chat activation rate and a 10-minute average session duration, expected peak concurrency is below 1 session. The system will not experience meaningful concurrency pressure under normal operating conditions.

**Test design:** Because observed concurrency is sub-1, a traffic-replication test provides no useful signal. The test is designed as a stress test against a fixed capacity target that provides a meaningful safety margin over expected load.

| Parameter | Value |
| --- | --- |
| Test type | Stress test (fixed concurrency, not traffic replay) |
| Target concurrent sessions | 10 (~40× expected peak production concurrency) |
| Sustained duration | 10 minutes at peak concurrency |
| Ramp-up | 2 minutes linear ramp to 10 concurrent sessions |
| Traffic pattern | Simulated visitor messages at realistic inter-message cadence (15–30s between turns) |
| RAG trigger rate | ~60% of turns trigger a `retrieve_knowledge` call |
| Test environment | Staging on Fly.io, same instance class as production (see Section 6.1) |
| Tooling | k6 or Locust — to be confirmed by engineering before Phase 5 |
| **Success criterion** | **p95 TTFT < 3s sustained across the full 10-minute window** |

**Re-evaluation trigger:** If corpus grows past 1M vectors, HNSW vector search performance must be re-benchmarked and index parameters (`m`, `ef_construction`, `ef_search`) re-tuned before the stress test is re-run against the larger index.

---

*Engineering concern resolved by this section: EC-09 — TTFT is confirmed as the target metric; full-response latency is explicitly out of scope. Load level is defined as 10 concurrent sessions based on observed site traffic (~100 visits/day, ~5/hour) and a 40× safety margin over expected peak concurrency.*
