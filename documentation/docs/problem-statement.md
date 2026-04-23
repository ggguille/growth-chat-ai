---
<description: "Formal problem definition for the AI-powered lead qualification chat — the output of the Discovery phase and the authoritative input to the PRD."
---

# Problem Statement

## AI-Powered Lead Qualification Chat

**Project:** AI-powered lead qualification chat
**Version:** 1.0
**Status:** Final — ready for PRD
**Last updated:** April 2026
**Author:** Product / AI Engineering Team

---

## Observed Problem

The company website receives consistent inbound traffic but fails to convert it into
qualified leads at an acceptable rate. Visitors browse services and case studies, then
leave without engaging. The only conversion mechanism is a static contact form —
passive, impersonal, and poorly suited to the consultative nature of the company's sales
process.

The form treats every visitor identically. It cannot distinguish a CTO actively
evaluating vendors from a curious researcher. It cannot answer questions, surface
relevant case studies, or create the kind of informed first impression that leads
to a sales conversation. It captures contact details but not context — leaving the
sales team to qualify cold from scratch.

---

## Hypothesis

An intelligent conversational interface can engage visitors at the moment of interest,
respond to their specific questions, qualify them progressively through natural
conversation, and convert more of them into leads that are ready for a sales
conversation.

**This hypothesis assumes** that the primary cause of low conversion is friction and
lack of engagement at the point of interest — not insufficient traffic, weak
positioning, or mismatched audience. This assumption is the central thing the MVP
exists to validate.

---

## Target Visitors

Three distinct visitor profiles represent the primary conversion opportunity.
Full definitions in [User Personas](./user-personas/).

**P1 — The Evaluating CTO.** A senior technical decision-maker at a 50–500 person
company, actively comparing AI engineering vendors. High intent, low patience. Needs
technical depth and fast signal.

**P2 — The Exploring Founder.** An early-to-mid stage founder or product lead
exploring what AI engineering realistically costs and delivers. Lower immediate intent
but genuine potential. Needs education and trust before committing to a conversation.

**P3 — The Referred Decision-Maker.** A visitor who arrived via referral with high
intent and minimal resistance. Needs friction removed, not a qualification process.

Two additional visitor types — competitors gathering intelligence and curious
researchers — will be encountered but are explicitly not conversion targets.
Full definitions in [User Personas](./user-personas/).

---

## Proposed Solution — MVP

Build a conversational chat widget for the company landing page that:

- Responds to visitor questions about the company's services, expertise, and engagement
  models with the depth and confidence of a knowledgeable company representative.
- Qualifies visitors progressively through natural conversation, detecting fit across
  four dimensions: problem fit, authority fit, company fit, and timing fit.
- Captures lead information contextually — attached to a value exchange — never as
  a standalone form.
- Routes hot leads to the sales team in real time during business hours, with a
  structured capture and follow-up flow outside of hours.
- Provides value to visitors not yet ready to buy through relevant resources and
  honest answers, without pushing prematurely toward conversion.

The MVP scope is intentionally constrained. The objective is not to build the
complete system but to validate the core hypothesis with the minimum viable
implementation. Features deferred to v2 are defined in the PRD.

---

## Conversation Design Principles

Three strategic decisions made during Discovery govern how the system behaves.
Full rationale in the referenced documents.

**Helpfulness before capture** ([Chat Behaviour](./considerations/chat-behaviour.md)).
The chat earns the right to ask for contact information by being genuinely useful
first. It never gates a useful answer behind a sign-up. Qualification happens through
conversation, not interrogation.

**Signal-based qualification** ([Qualification Signals](./considerations/qualification-signals.md)).
The system builds a picture of the visitor incrementally by extracting fit signals
from natural language. It escalates when the picture is clear enough — not before,
not after.

**Clean handoff with context** ([Human Handoff](./considerations/human-handoff.md)).
When a human is needed, the transition is immediate, contextual, and complete.
The visitor never repeats themselves. The sales team receives a structured summary
of the conversation alongside the lead.

---

## Out of Scope

The following are explicitly outside the boundaries of this project:

- Support channel for existing clients.
- Replacement for the sales team or autonomous deal closing.
- CRM integration in v1.
- A/B testing framework in v1 — requires a baseline before experimentation.
- Active competitor detection — handled through defensive design, not detection logic.

---

## Success Metrics — MVP

The MVP validates the hypothesis if it achieves the following within 90 days
of launch:

| Metric | Target | How measured |
| --- | --- | --- |
| Lead qualification rate | Chat leads reach sales call at a higher rate than form submissions | CRM comparison: chat leads vs. form leads over 90 days |
| Contact capture rate | % of chat conversations that result in an email captured | Chat analytics |
| Hot lead response time | < 5 minutes during business hours from detection to sales notification | Handoff system logs |
| Visitor satisfaction signal | Conversations reach Stage 3 (proposal) in > 30% of qualifying interactions | Conversation state analytics |

A formal go/no-go decision on v2 investment will be made at the 90-day mark
based on these metrics.

---

## Discovery Documents

This Problem Statement is the output of a structured Discovery process.
The following documents support and inform it:

| Document | Content |
| --- | --- |
| [User Personas](./user-personas/) | Five visitor personas — three target, two negative |
| [Chat Behaviour](./considerations/chat-behaviour.md) | Conversation model and lead capture principles |
| [Qualification Signals](./considerations/qualification-signals.md) | Qualification dimensions, scoring model, escalation logic |
| [Human Handoff](./considerations/human-handoff.md) | Handoff triggers, execution sequences, escalation matrix |

---

## What This Is Not

This document is not a specification. It does not define how the system is built,
what technology is used, or what the conversation flows look like in detail.
Those decisions belong to the PRD and the technical architecture documents that
follow it.

This document answers one question: **is this the right problem to solve, and is
this the right direction for solving it?**

The answer, based on Discovery, is yes.

---

*This Problem Statement supersedes v1.0 (the original discovery artifact).
It reflects the decisions made during the Discovery phase and serves as the
authoritative input to the PRD.*
