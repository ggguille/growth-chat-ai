---
description: "Design considerations for the Growth Chat system — answers to the open questions raised in the discovery artifact."
---

# Considerations

**Project:** AI-powered lead qualification chat
**Version:** 1.0
**Status:** In Progress
**Last updated:** April 2026

---

## Overview

This section documents the answers to the design questions raised in the [Discovery Artifact](../discovery-artifact.md). Each consideration explores a specific tension or decision that shapes how the chat system is built and behaves. Documents are added as decisions are made.

---

## Things to Consider

| # | Topic | Question | Document | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| 1 | Helpfulness vs. lead capture | How do you balance helpfulness with lead capture? | [Chat Behaviour](./chat-behaviour.md) | Answered | |
| 2 | Qualification signals | What qualification signals matter? | [Qualification Signals](./qualification-signals.md) | Answered | |
| 3 | Human handoff | When does the bot hand off to a human? | [Human Handoff](./human-handoff.md) | Answered | |
| 4 | Competitor handling | How do you handle competitors asking questions? | [N1 Competitor §Chat Strategy](../user-personas/n1-competitor.md#chat-strategy) | Partial | Covers competitor-specific strategy; no standalone consideration doc |
| 5 | Chat personality | What personality should the chat have? | [Chat Behaviour §Design Principle](./chat-behaviour.md#design-principle) | Partial | Principle defined; per-persona tone adaptation not consolidated |
| 6 | Pricing questions | How do you handle pricing questions? | [N1 Competitor §Chat Strategy](../user-personas/n1-competitor.md#chat-strategy) | Partial | Covers competitor probes only; genuine lead pricing guidance pending |
| 7 | Case study contextualisation | Should the chat know about specific case studies and reference them contextually? | — | Pending | |
| 8 | Contact capture | How do you capture email/contact info without feeling like a form? | [Chat Behaviour §Contact Information](./chat-behaviour.md#contact-information--when-and-how-to-ask) | Partial | Covers when/how to ask; contextual variation by persona not detailed |
| 9 | Out-of-hours behaviour | What happens outside business hours? | [Human Handoff §Outside Business Hours](./human-handoff.md#handoff-execution--outside-business-hours) | Partial | Covered as subsection of handoff; no standalone decision doc |
| 10 | A/B testing | How do you A/B test different approaches? | — | Pending | |
| 11 | Support channel prevention | How do you prevent the chat from becoming a support channel for existing clients? | [Human Handoff §Trigger 3](./human-handoff.md#trigger-3--question-out-of-scope), [N2 Curious Researcher §Chat Strategy](../user-personas/n2-curious-researcher.md#chat-strategy) | Partial | Routing defined; proactive prevention strategy not addressed |

---

*Questions sourced from the [Discovery Artifact](../discovery-artifact.md). Each answered document records the decision, the reasoning, and the implications for the PRD.*
