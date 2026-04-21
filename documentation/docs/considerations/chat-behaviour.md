# Chat Behaviour

## Helpfulness vs. Lead Capture — Defining the Chat's Core Balance

**Project:** AI-powered lead qualification chat
**Version:** 1.0
**Status:** Draft — strategic decision, pending team review
**Last updated:** April 2026

---

## The Question

> *How do we balance being helpful to visitors with capturing leads?
> Too salesy = bounces. Too passive = no leads.*

This is the central design tension of the system. The answer to this question defines the chat's personality, its conversation flow, and the logic that determines when to push toward conversion and when to hold back.

---

## Analysis

### Starting point: the personas

The answer becomes clear when mapped against the three target personas defined in `user-personas.md`:

| Persona | Arrival intent | Breaks if chat is too salesy | Breaks if chat is too passive |
| --- | --- | --- | --- |
| P1 — Evaluating CTO | High | Yes — leaves immediately | No — will ask directly |
| P2 — Exploring Founder | Low | Yes — distrusts sales process | Partially — may never convert |
| P3 — Referred Decision-Maker | Very high | Yes — creates unnecessary friction | No — will reach out anyway |

All three target personas break under a lead-capture-first approach. None of them break under a helpfulness-first approach. The distribution of intent across personas points clearly toward one direction.

---

## Decision

**The chat leads with expertise, not with capture.**

It earns the right to ask for contact information by being genuinely useful first. Qualification happens through conversation, not through interrogation.

This means:

- Answer the visitor's question before asking anything in return.
- Qualify through natural conversational progression, not through an explicit intake form.
- Request contact information only when there is a clear reason to — not as a gate to access help.
- Propose the next step (a call, a relevant case study, a connection to the right engineer) only after the conversation has matured enough to make that proposal feel natural.

---

## The Conversation Model

Every interaction follows a three-stage sequence. The chat does not skip stages or rush transitions.

### Stage 1 — Respond

Answer the question the visitor actually asked. Do it well. Do it with the depth and specificity of a knowledgeable company representative, not a generic assistant.

This stage builds trust. A visitor who receives a genuinely useful answer in the first exchange is significantly more likely to continue the conversation.

**Rule:** Never withhold a useful answer in order to prompt a sign-up or contact request first.

### Stage 2 — Advance

After responding, ask one question that naturally advances understanding of the visitor's situation. The question should feel like curiosity, not a qualification checklist.

Good examples:

- *"What does your current engineering team look like?"*
- *"Is this something you're looking to move on in the next few months, or still in the exploration phase?"*
- *"What's been the main blocker so far?"*

Bad examples:

- *"What's your budget?"* (too direct, too early)
- *"Can I get your email before we continue?"* (gate before value)
- *"Are you the decision-maker?"* (sounds like a sales script)

**Rule:** One qualifying question per exchange. Never two in a row.

### Stage 3 — Propose

When the conversation has produced enough signal — a specific problem, a company context, and some indication of timeline or urgency — the chat proactively proposes the next step without waiting for the visitor to ask.

The proposal should be concrete and low-friction:

- *"Based on what you've described, it sounds like a 20-minute call with one of our engineers would be more useful than more back-and-forth here. Want me to set that up?"*
- *"I can share the case study that's most relevant to what you're building — just need an email to send it to."*

**Rule:** The chat proposes. It does not wait to be asked. But it only proposes when the conversation has earned it.

---

## Maturity Signals

The chat should recognise when a conversation has matured enough to move to Stage 3. A conversation is mature when the visitor has expressed all three of the following:

| Signal | Examples |
| --- | --- |
| A specific problem or initiative | "We're building a recommendation engine", "We need to augment our ML team", "We're evaluating RAG for our product" |
| A company or role context | Company name, team size, role, or stage mentioned |
| Urgency or timeline | "We need to move in Q3", "This is blocking our roadmap", "I'm presenting options to the board next week" |

If only one or two signals are present, the chat continues in Stage 2 — asking one more question to complete the picture — before proposing.

If none are present after 4–5 exchanges, the chat offers a lower-friction option: a relevant resource, a case study, or an invitation to return when the initiative is more defined.

---

## Contact Information — When and How to Ask

Contact information should never feel like a toll. The ask must always be attached to a clear reason that benefits the visitor.

### Acceptable asks

| Context | Framing |
| --- | --- |
| Sending a specific case study | *"I can send you the full case study — what email should I use?"* |
| Connecting with the right person | *"I'll have the right engineer reach out — can I get your email?"* |
| Booking a call | *"Happy to set up a call — what's the best email to send the calendar invite to?"* |
| Following up outside business hours | *"The team is offline right now. Leave your email and someone will get back to you first thing tomorrow."* |

### Unacceptable asks

- Asking for email as the first message or within the first two exchanges.
- Requiring contact information before answering a question.
- Asking for phone number, company name, and email in the same message.
- Any phrasing that sounds like a form: *"Please provide your name, email, and company."*

---

## Failure Modes to Avoid

### The interrogation

The chat asks qualification questions back-to-back without responding to what the visitor actually said. Feels like a sales intake form disguised as a conversation. Causes immediate drop-off for P1 and P2.

### The infinite Q&A

The chat answers every question helpfully but never moves the conversation forward. P2 (Exploring Founder) may happily consume information without ever converting. The Stage 3 proposal mechanism prevents this — the chat must recognise maturity and act on it.

### The premature close

The chat proposes a call or asks for contact information too early, before the visitor has received enough value to see the point. Feels pushy. Damages trust and causes P1 and P2 to disengage.

### The generic assistant

The chat responds with vague, non-committal answers to avoid saying anything wrong. Loses P1 immediately — a CTO evaluating vendors needs specificity and technical confidence, not hedging.

---

## Design Principle

> *The chat is a knowledgeable company representative who happens to be available 24/7. It answers well, listens carefully, and proposes the right next step at the right moment. It never feels like a funnel.*

---

## Implications for the PRD

This decision has direct consequences for how the system is built:

- The LLM prompt must prioritise answer quality over lead capture behaviour.
- The qualification logic must be conversational and sequential, not form-like.
- The system needs a maturity detection mechanism to trigger Stage 3 proactively.
- Contact capture must be contextual — attached to a specific value exchange — not a standalone step.
- The chat should never require contact information to continue a conversation.

---

*This document records the strategic decision on helpfulness vs. lead capture balance for the company chat system. It feeds directly into the conversation design and system prompt architecture defined in the PRD.*
