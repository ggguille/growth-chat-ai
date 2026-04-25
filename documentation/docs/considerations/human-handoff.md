---
description: "Defines the four triggers for handing off to a human — hot lead detected, explicit request, out-of-scope question, conversation stall — and the execution sequences for in-hours and outside-hours scenarios."
---

# Human Handoff

## When the Chat Stops and a Person Begins

**Project:** AI-powered lead qualification chat
**Version:** 1.0
**Status:** Final
**Last updated:** April 2026

---

## The Question

> *When does the bot hand off to a human?
> Hot lead? Complex question? Explicit request?*

This question defines the boundaries of the system. Where the chat ends and the sales team begins — and how that transition happens without the visitor experiencing it as a disruption or a dead end.

---

## A Critical Distinction

There are two types of handoff. They are frequently conflated, but they have different triggers, different goals, and different implementation requirements.

**Escalation handoff** — the chat has detected a hot lead and actively transfers the conversation to a human. The objective is speed. The faster the transition from detection to human contact, the higher the conversion rate. Every minute of delay after a hot lead is detected reduces the probability of conversion.

**Capture handoff** — the chat cannot complete the conversation right now (outside business hours, question out of scope, visitor explicitly requests a human) but collects the information needed for a human to follow up later. The objective is not to lose the lead. The visitor leaves knowing exactly when and how they will hear back.

Both types must be handled well. Failing at escalation handoff loses hot leads in the moment. Failing at capture handoff loses leads that arrived at the wrong time or with the wrong question.

---

## Handoff Triggers

There are four conditions that should trigger a handoff. They are ordered by priority.

---

### Trigger 1 — Hot Lead Detected

**Condition:** The qualification scoring model defined in `p3-qualification-signals.md` confirms a hot lead: problem fit confirmed + authority fit confirmed + at least one of (company fit / timing fit).

**Type:** Escalation handoff.

**Response:** Immediate. The chat does not wait for additional confirmation or ask more qualifying questions. It surfaces the proposal within the same exchange in which the threshold is crossed.

**Framing:**
> *"Based on what you've described, it sounds like a conversation with one of our engineers would be much more useful than more back-and-forth here. They can give you specific answers on [the initiative mentioned]. Want me to connect you?"*

**What must not happen:** The chat detects a hot lead and continues asking qualification questions. This is the most common failure mode in chat systems — the logic keeps running past the point where a human should have taken over.

---

### Trigger 2 — Explicit Visitor Request

**Condition:** The visitor asks to speak with a person. Any phrasing that expresses this intent should trigger the handoff immediately.

**Type:** Escalation handoff (during hours) or capture handoff (outside hours).

**Example phrases that trigger this:**

- "Can I speak to someone on your team?"
- "Is there an engineer I can talk to?"
- "I'd rather just book a call"
- "Can you connect me with sales?"
- "Who should I talk to about this?"

**Response:** Immediate. No additional qualification. No "before I connect you, can I ask a couple of questions." If a visitor requests a human, give them a human.

**Rule:** An explicit request for a human overrides the qualification state. Even a visitor classified as cold or warm by the scoring model should be escalated if they explicitly ask. The cost of refusing a human request is higher than the cost of an occasional unqualified escalation.

---

### Trigger 3 — Question Out of Scope

**Condition:** The visitor asks something the chat cannot or should not answer. This includes:

| Category | Examples |
| --- | --- |
| Existing client support | "I'm already working with the company and have an issue with my team" |
| Specific contract or commercial terms | "What would the exact cost be for a 6-month engagement?" |
| Sensitive internal information | Questions about specific employees, internal processes, or non-public information |
| Legal or compliance questions | Questions about NDAs, IP ownership, or contractual liability |
| Highly technical scoping | Questions requiring a detailed technical assessment that the chat cannot perform accurately |

**Type:** Capture handoff, with routing to the appropriate person (sales, account management, legal).

**Response:** Acknowledge the limit clearly and without apologising excessively. Explain who the right person is and how the visitor will be connected.

> *"That's a question I can't answer accurately here — it depends on specifics that really need a direct conversation. I can connect you with [the right person] who can give you a proper answer. What's the best email to reach you?"*

**What must not happen:** The chat attempts to answer a question it cannot answer well in order to avoid admitting a limitation. A wrong or vague answer to a contract or pricing question damages trust more than a clean handoff.

---

### Trigger 4 — Conversation Stall or Visitor Frustration

**Condition:** The conversation has stalled or the visitor is showing signals of frustration or dissatisfaction.

**Stall signals:**

- The visitor repeats the same question after receiving an answer
- The conversation has run more than 6–8 exchanges without reaching a Stage 3 proposal
- The visitor responds with very short, non-committal answers for two or more consecutive exchanges

**Frustration signals:**

- Explicit expressions of frustration ("this isn't helpful", "you're not answering my question")
- Short dismissive responses after a detailed answer
- The visitor attempts to end the conversation

**Type:** Capture handoff attempt.

**Response:** Do not try to recover the conversation alone. Acknowledge the situation and offer a human directly.

> *"I don't think I'm giving you what you need here. Would it be more useful to speak directly with someone from the team? I can make sure they have context from our conversation so you don't have to repeat yourself."*

**What must not happen:** The chat continues attempting to engage a frustrated or stalled visitor with more questions or longer answers. This compounds the frustration and accelerates exit.

---

## Handoff Execution — During Business Hours

A handoff during business hours should feel like a natural transition, not an interruption. The quality of the handoff determines whether the visitor converts or drops off at the last step.

### The three-step handoff sequence

**Step 1 — Summarise**
Before proposing the handoff, the chat briefly reflects back what it has understood. This serves two purposes: it confirms to the visitor that the conversation was understood, and it begins building the context packet that will be transferred to the sales team.

> *"So just to make sure I have this right — you're building [X], your team currently [Y], and you're looking to move on this by [Z]. Does that sound right?"*

**Step 2 — Propose with context**
Frame the handoff as a benefit to the visitor, not as a limitation of the chat. Reference what the human will be able to do that the chat cannot.

> *"A conversation with one of our engineers would let you get into the specific technical decisions around [X] — that's not something I can give you a good answer on. It's usually a 20-minute call and people find it genuinely useful even if they're not ready to move forward yet."*

**Step 3 — Collect the minimum**
Ask for the minimum information needed to make the connection. Email is required. Phone number and preferred time slot are optional but useful.

> *"What's the best email to send the calendar invite to?"*

Do not ask for name, company, role, and phone number in the same message. Collect what is needed and nothing more.

### Context transfer requirement

The visitor must never have to repeat themselves to the sales team. When a handoff occurs, the system must transfer a context packet containing:

| Field | Content |
| --- | --- |
| Conversation summary | 3–5 sentence summary of the key points discussed |
| Qualification state | Which of the four dimensions were confirmed and at what confidence level |
| Lead level | Hot / warm / cold at the time of handoff |
| Trigger | What caused the handoff (hot lead detected / explicit request / out of scope / stall) |
| Visitor-provided data | Email, name, company, role — whatever was collected |
| Timestamp and session data | When the conversation occurred, platform, page the visitor was on |

---

## Handoff Execution — Outside Business Hours

Outside business hours is where most chat systems fail. A visitor with high intent who arrives at 11pm or on a weekend has three options: leave their details and wait, go to a competitor who responds faster, or leave without doing anything. The chat determines which of the three happens.

### The outside-hours handoff sequence

**Step 1 — Be transparent about availability**
Do not pretend the team is available when it is not. Do not use vague language like "our team will get back to you soon." Be specific.

> *"Our team is offline right now — we're based in Europe, so we're typically available Monday to Friday, 9am–6pm CET."*

**Step 2 — Make a specific commitment**
A vague promise of follow-up is nearly as bad as no promise. Give the visitor a specific expectation.

> *"If you leave your email now, someone from the team will reach out tomorrow morning before 10am CET."*

**Step 3 — Offer immediate value**
The visitor arrived now for a reason. Give them something useful while they wait — a relevant case study, a technical guide, or a resource that addresses the question they came with.

> *"While you wait, I can send you the case study most relevant to what you've described — it covers a similar project we delivered for a fintech team. Would that be useful?"*

### The timezone advantage

The company's European timezone coverage is explicitly part of its positioning. Outside-hours conversations with US-based visitors are an opportunity to reinforce this differentiator rather than apologise for the time difference.

> *"Our engineering team is based in Europe — which means when your day is winding down, they're already starting fresh on your project the next morning. A lot of our US clients actually find that cadence works really well."*

This framing converts a potential objection (they're not available right now) into a product feature (they work while you sleep).

---

## What the Chat Must Never Do

| Action | Why it is wrong |
| --- | --- |
| Detect a hot lead and keep asking questions | The escalation threshold has been crossed. More questions delay conversion and risk losing the visitor. |
| Refuse an explicit request for a human | Even a cold visitor who asks for a human gets a human. The cost of refusing is higher than the cost of an unqualified escalation. |
| Hand off without transferring context | Forces the visitor to repeat themselves. Destroys the trust built during the conversation. |
| Promise a response time the team cannot meet | A broken promise is worse than no promise. Only commit to timelines that can be guaranteed. |
| Escalate negative personas (N1, N2) to sales | Wastes sales team time. Competitive visitors and researchers should never trigger escalation. |
| Attempt to recover a stalled conversation alone | Continuing to engage a frustrated visitor with more questions compounds the problem. Offer a human. |

---

## Escalation Matrix

| Trigger | Visitor type | Business hours | Outside hours |
| --- | --- | --- | --- |
| Hot lead detected | P1, P2, P3 | Immediate escalation — offer call or connection | Capture handoff — specific follow-up commitment + resource |
| Explicit human request | Any (including N1, N2) | Immediate escalation | Capture handoff — explain availability, commit to follow-up |
| Out of scope question | Any | Route to appropriate contact (sales / account mgmt / legal) | Capture handoff with routing note for the right person |
| Conversation stall / frustration | Any | Offer human immediately | Acknowledge, capture email, offer resource |
| Warm lead after 6+ exchanges | P2 primarily | Soft escalation — offer lower-friction option (case study, resource) | Capture email with nurture resource |

---

## Implications for the PRD

- The system needs a real-time availability signal — the chat must know whether it is inside or outside business hours for the company's team, accounting for timezone and public holidays.
- The escalation trigger must be programmatic and based on the qualification state object from P3, not left to the LLM to decide conversationally.
- A context packet schema must be defined and implemented — this is what gets sent to the CRM or sales notification system at the point of handoff.
- The outside-hours flow requires a specific conversation path distinct from the standard flow — not a fallback message, but a designed experience.
- Negative persona detection (N1, N2) must be part of the escalation gate — the system should not escalate to sales regardless of other signals if the visitor is classified as a competitor or researcher.

---

## Sales Team Findings

The following questions were raised during the design phase and validated by the sales team.

---

### What is the current average response time to form submissions?

Current baseline: 24–48 hours to a substantive reply on business days. The first automated acknowledgement goes out within minutes, but the first real human response averages 6–8 hours on a good day — longer on Mondays and after public holidays. The chat handoff must beat 6 hours for hot leads during business hours to be meaningfully better than the existing form.

**Implication for the chat:** The escalation notification must reach a human immediately — not batched or in a daily digest. A hot lead detected at 10am CET should generate a Slack ping and a CRM task within seconds, not in a morning summary email.

---

### Who specifically receives the escalation notification?

No single owner exists today. Form submissions go to a shared `sales@` inbox monitored by two people during CET hours. The notification from the chat should replicate that pattern initially: a Slack message to `#new-leads` for immediate visibility, plus a task created in the CRM assigned to whoever is on commercial duty that day. A dedicated escalation routing rule — based on company size or geography — is a V2 concern.

**Implication for the chat:** The context packet must be delivered to two destinations simultaneously: Slack (`#new-leads`) and the CRM. The CRM task should be pre-populated with the full context packet so the rep does not need to retrieve the Slack thread.

---

### What is the preferred format for the context packet?

Email summaries are not actionable fast enough. The preferred format is:

- **Slack notification** (primary, for speed): Headline with lead level, visitor-provided data, and a 2–3 sentence summary. Linked to the full CRM record.
- **CRM note** (primary, for record): Full context packet fields as a structured note on a new contact record. This is the audit trail.
- **Email to `sales@`** (secondary, as fallback): Only if Slack or CRM integration is unavailable. Not the preferred channel.

Phone-based notification (SMS, WhatsApp) is not needed in V1 — the team monitors Slack reliably during business hours.

**Implication for the chat:** The system needs a CRM integration and a Slack webhook as V1 requirements, not optional add-ons. Email-only delivery is insufficient for the response-time target.

---

### Are there times when the sales team is available outside standard CET hours?

No structured US-hours coverage exists today. Individual team members are sometimes reachable outside CET hours for existing key accounts, but this is ad hoc and should not be surfaced to new visitors as a commitment.

The outside-hours flow must not imply 24/7 availability. The specific availability window to state is **Monday–Friday, 9am–6pm CET**, with the follow-up commitment of **next business morning before 10am CET**. The timezone advantage framing (working while US clients sleep) is accurate for delivery teams and can be used — but the sales and commercial team operates on CET hours.

**Implication for the chat:** Do not offer same-day follow-up for conversations that arrive after 4pm CET — the turnaround cannot be guaranteed. The "before 10am CET next business morning" commitment is the right bar: specific, reliable, and better than the existing form baseline.

---

### Should the chat offer self-serve calendar booking (e.g. Calendly) for hot leads?

Use Calendly for hot leads, not for warm leads.

A hot lead who has confirmed problem fit, authority fit, and at least one further dimension is ready to move. Adding a human scheduling step introduces 12–24 hours of unnecessary delay. A direct Calendly link to a 30-minute intro call — with the context summary pre-populated in the booking notes — is the right path for these visitors.

For warm leads (capture handoff), human follow-up is preferred. The rep should reach out to set the agenda and select the right engineer for the call. That pre-call preparation is part of the qualification the rep does before the first meeting, and it cannot happen if the visitor self-books before the rep has reviewed the context.

The Calendly link should route to a shared calendar with two-day advance booking minimum, to give the assigned rep time to review the context packet before the call.

**Implication for the chat:** The system needs a Calendly link configured for hot lead escalations. This is a V1 requirement alongside the Slack and CRM integrations. For capture handoffs, the flow ends with email collection — no self-serve booking is offered.

---

*This document records the strategic decision on human handoff logic for the chat system. It defines the four handoff triggers, the execution sequence for both in-hours and out-of-hours scenarios, and the context transfer requirements. It feeds directly into the escalation architecture and CRM integration defined in the PRD.*
