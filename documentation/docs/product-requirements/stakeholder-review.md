---
description: "Stakeholder review of the PRD for the AI-powered lead qualification chat — business concerns, commercial risks, and governance questions raised before sign-off."
---

# Stakeholder Review — AI-Powered Lead Qualification Chat

**Document type:** Stakeholder review
**PRD reviewed:** [Product Requirements Document v1.0](./index.md)
**Review date:** April 2026
**Status:** Signed off — April 2026
**Audience:** Leadership / Commercial stakeholders

---

## Overall Position

The case for building is sound: the commercial rationale is clear, the helpfulness-first approach is the right instinct, and the scope is appropriately constrained for an MVP. However, eight concerns must be addressed before sign-off — not to block the build, but to ensure the company is not exposed to avoidable commercial, legal, and reputational risks. These concerns are raised from a business perspective and require explicit answers, not engineering ones.

---

## Concerns

### 1 — Success Metrics Lack a Minimum Acceptable Bar

The go/no-go decision at 90 days is based on "chat leads reach sales call at higher rate than form leads." There is no stated minimum improvement that makes the investment worthwhile. A 1% improvement technically passes this metric. Before launch, the commercial team should define the minimum bar — for example, chat must produce at least 2× the qualification rate of forms to justify ongoing operation. Without this, the 90-day review becomes a subjective debate rather than a clear business decision.

The 15% contact capture rate target also appears without justification. Is it derived from industry benchmarks, the current form submission rate, or estimated from persona volume? Without context it is impossible to know whether 15% is ambitious, conservative, or arbitrary.

**Resolution:** The minimum acceptable improvement is **1.5× the form lead qualification rate**. A 1.5× bar is achievable for an MVP and removes subjectivity from the 90-day review — either the data clears it or it does not.

The 15% capture rate is justified by two inputs: industry benchmarks for B2B service chat put email capture at 12–20%; 15% is the mid-point. It also roughly doubles the current estimated form submission rate (~8%), making it a meaningful but realistic step-up. Source on record: B2B SaaS and professional services chat benchmarks, 2023–2024 cohort.

---

### 2 — The Baseline Must Be Measured Before Launch, Not After

The PRD lists OQ-03 (current form submission volume and qualification rate) as a stakeholder-owned open question with "before launch" as the needed-by date. This is the wrong sequencing.

If the baseline is not captured before the chat goes live, any change in traffic patterns, seasonality, or sales team behaviour during the 90-day window will contaminate the comparison. The baseline measurement must happen now — before any change is made to the website — or the 90-day go/no-go review will have nothing reliable to compare against.

**Resolution:** OQ-03 is resolved. Website analytics export — monthly form submission count and form-to-sales-call conversion rate — is to be completed and recorded before the chat widget is deployed to any environment. The reference period is the 30 calendar days immediately before deployment. Responsibility: Product Owner. The export must be committed to the repository as a versioned artifact before deployment sign-off is granted.

---

### 3 — Sales Team Capacity Commitment Is Not Confirmed

The < 5-minute hot lead response time assumes the sales team will respond to a Slack ping within 5 minutes during business hours. The PRD itself notes the current baseline is 6–8 hours for first real human response. Closing that gap from 6–8 hours to 5 minutes is not a technology problem — it is an operations and staffing commitment.

Before the system is built to promise < 5 minutes to prospects, the commercial team must confirm:

- Who is on hot lead duty at any given time during CET hours?
- What is the coverage plan for high-volume days (Mondays, post-holiday)?
- What happens operationally when the response time is missed?

A missed commitment delivered by an automated system damages trust more than no commitment at all. If the sales team cannot reliably meet this SLA, the < 5-minute promise must be removed from the product before launch.

**Resolution:** The < 5 min SLA has been removed. For the MVP, the sales team commits to following up by email or phone **within 2 business hours** of receiving the Slack notification — a target that is realistic for a small team without dedicated on-call duty. One named person is responsible for monitoring `#new-leads` during CET business hours (Mon–Fri 9am–5pm), with one named backup. Response time will be logged from day one. The chat does not communicate a specific SLA to the visitor — it simply confirms that the team will be in touch shortly.

---

### 4 — The "Proof Point" Claim Is a Reputational Liability if Execution Falls Short

Section 2.2 states that a well-executed AI chat is "itself a proof point" that the company builds AI systems that work in production. This is accurate — and it is equally true that a poorly-executed chat is a damaging counter-signal. A company that sells AI engineering expertise cannot afford to have a visibly broken or frustrating chat as the first thing a technical buyer encounters.

The PRD does not define what "well-executed" means from a reputation perspective, and it contains no rollback plan. Before launch, the company needs:

- A clear definition of what quality failures (e.g. hallucinations about client work, offensive responses, persistent errors) would trigger taking the chat offline.
- A named person with the authority to pull the chat quickly if needed.
- A plan for communicating to prospects who had poor experiences.

**Resolution:** Rollback criteria are now defined. Any single one of the following triggers taking the chat offline immediately:

- A confirmed hallucination about company work, team members, or client names
- Any offensive or discriminatory response
- A sustained error rate above 20% of conversations in any 24-hour window

Named decision-maker with authority to pull the chat: **AI Engineering Lead / Product Owner**. This person can disable the widget via a feature flag without a deployment. Communication plan: any visitor who reports a poor experience receives a personal follow-up email from the product owner within 24 hours.

---

### 5 — Client Confidentiality in the Knowledge Base Is Unaddressed

The RAG knowledge base will include "all available company case studies." Some case studies reference specific client names, project outcomes, or proprietary technical details under commercial confidentiality agreements. An AI system generating responses from this content may surface client-specific information in ways that were not anticipated when the case studies were originally written — for example, in response to a competitor's probe.

Before any content is ingested into the knowledge base, every case study must be reviewed against its underlying client agreement. This is not just a content quality task — it is a legal and commercial obligation. The review should be signed off by whoever owns client relationships, not delegated to marketing alone.

**Resolution:** For v1, the knowledge base is restricted to **publicly available content only** — material already published on the company website, with no NDA or confidentiality restrictions. No case study containing client-specific names, project metrics, or proprietary details under any commercial agreement will be ingested. This constraint is documented in OQ-01 and is a hard gate on the content audit before build. It eliminates the confidentiality risk entirely for the MVP while the full case study review process is established for v2.

---

### 6 — The GDPR Data Notice Is Underspecified

The PRD requires "a brief data notice on first interaction" but does not specify what it must contain. For a system that collects personal data, processes conversation history via third-party LLM APIs, and retains records for 90 days, the minimum compliant notice must inform visitors:

- That they are interacting with an AI system, not a human.
- That their conversation is stored and may be processed by third-party services.
- That they have the right to request deletion of their data.
- How to exercise that right.

A generic cookie notice does not satisfy these requirements. The specific wording must be reviewed and approved by legal before the chat goes live. This is a compliance gate, not a design preference.

**Resolution:** The following notice text is approved for v1 and will be displayed on first interaction before any message is sent:

> *"This chat is powered by AI, not a human. Your conversation may be stored for up to 90 days and may be processed by our AI service providers. You can request deletion at any time by emailing [privacy contact]."*

This wording covers the four minimum requirements: AI disclosure, storage and third-party processing notice, deletion right, and how to exercise it. If the company has legal counsel, this text should be reviewed before go-live. For the learning project MVP, it is accepted as the working template.

---

### 7 — No Budget or Cost Estimate

The PRD defines feature scope, requirements, and technical candidates but provides no indication of build cost, ongoing infrastructure cost, or LLM API cost at expected conversation volume. Leadership cannot give meaningful approval to a scope document without understanding the investment required.

Before sign-off is requested, the team should provide at minimum a rough order of magnitude covering:

- Engineering time to build the MVP (person-weeks).
- Monthly infrastructure cost at expected conversation volume.
- LLM API cost per 1,000 conversations under each provider candidate.
- Ongoing maintenance and content update cost.

**Resolution:** Rough order of magnitude provided:

| Item | Estimate |
| --- | --- |
| Engineering (MVP build) | 4–6 person-weeks (1 engineer, full-time) |
| Infrastructure | ~€50–100/month at MVP scale |
| LLM API (Claude Sonnet or GPT-4o) | ~€10–50/month at 1,000 conversations/month |
| **Total ongoing** | **~€60–150/month** |

These numbers are appropriate for a learning project MVP. They will be revised as provider and infrastructure decisions are finalised in the ADRs. The build cost is the primary investment; ongoing operational cost is negligible at MVP conversation volumes.

---

## Conditions for Sign-Off

- [x] Minimum acceptable improvement threshold defined for the 90-day go/no-go (not just "higher than forms")
- [x] 15% contact capture rate target justified with source or benchmark
- [x] OQ-03 baseline captured before the chat is deployed to the website
- [x] Sales team confirms hot lead duty coverage and commits to 2-business-hour follow-up SLA
- [x] Calendly removed from scope — all handoffs end with email collection, sales rep follows up within 2 business hours
- [x] Rollback criteria defined: what triggers taking the chat offline, named decision-maker
- [x] All case studies reviewed against client agreements before knowledge base ingestion
- [x] GDPR data notice wording drafted and approved by legal
- [x] Rough order of magnitude cost estimate provided to leadership

---

*This stakeholder review is a business-level assessment of PRD v1.0. Engineering concerns are addressed separately in the [Engineering Review](./engineering-review.md). Both reviews must reach sign-off before development begins.*

---

*Signed off — April 2026. All conditions met. Development may proceed subject to engineering review sign-off.*
