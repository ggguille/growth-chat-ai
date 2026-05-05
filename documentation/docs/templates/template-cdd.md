# Conversation Design Document
## [System / Feature Name]

**Project:** [Project name]
**Version:** 1.0
**Status:** `Draft` | `In Review` | `Approved`
**Last updated:** YYYY-MM-DD
**Author:** [Conversation Designer / PM / AI Engineer]
**Reviewers:** [Roles]

> **What this document is:**
> The Conversation Design Document (CDD) specifies how the system behaves
> in conversation — what it says, when, and why. It is the primary input
> for system prompt engineering, LLM instruction design, and QA test case
> generation. It sits between the PRD (what the system does) and the TRD
> (how it is built technically).
>
> **Who uses it:**
> - AI Engineer — writes the system prompt from this document
> - QA — generates test conversations from the dialogue examples
> - PM — validates that the designed behaviour matches product intent
> - Sales / subject matter experts — reviews tone and content accuracy

---

## 1. Conversation Principles

<!--
3–6 high-level principles that govern all conversation design decisions.
These are the rules the system always follows, regardless of context.
Each principle should be actionable — specific enough that it can
be used to make a design decision or evaluate a response.

Anti-pattern: "Be helpful and friendly" — too vague, not actionable.
Good pattern: "Answer the visitor's question before asking anything
in return — never gate a useful response behind a sign-up or
qualifying question." — specific, actionable, testable.
-->

1. **[Principle name]** — [Description. Specific enough to make a design decision.]
2. **[Principle name]** — [Description.]
3. **[Principle name]** — [Description.]

---

## 2. Conversation Model

### 2.1 Stage Structure

<!--
Define the stages of a conversation and the rules for moving between them.
Every AI conversation system has stages, even if they are not explicitly named.
Making them explicit allows the system prompt to enforce them reliably.

For each stage, specify:
- Name and purpose
- Entry condition (what triggers this stage)
- Behaviour rules (what the system does and does not do)
- Exit condition (what moves the conversation to the next stage)
-->

| Stage | Purpose | Entry condition | Exit condition |
|---|---|---|---|
| [Stage 1 name] | [What the system is doing] | [What triggers it] | [What ends it] |
| [Stage 2 name] | [What the system is doing] | [What triggers it] | [What ends it] |
| [Stage 3 name] | [What the system is doing] | [What triggers it] | [What ends it] |

### 2.2 Stage Rules

#### Stage 1 — [Name]

**The system must:**
- [Rule 1]
- [Rule 2]

**The system must not:**
- [Anti-rule 1]
- [Anti-rule 2]

**Example — good:**
```
Visitor: [example message]
System:  [example response that follows the rules]
```

**Example — bad (and why):**
```
Visitor: [example message]
System:  [example response that breaks a rule]
// ❌ Why this is wrong: [explanation]
```

#### Stage 2 — [Name]

[Same structure as Stage 1]

#### Stage 3 — [Name]

[Same structure as Stage 1]

---

## 3. Persona and Tone

### 3.1 Overall Voice

<!--
Define the personality of the system in concrete, behavioural terms.
Avoid abstract adjectives ("professional", "friendly") — they mean
different things to different people.
Instead, use comparisons and contrasts:
"The register of a senior engineer talking to a peer — not a sales
assistant reading from a script."

Include:
- What the voice IS
- What the voice IS NOT
- Specific vocabulary guidance (words to use / avoid)
-->

**The system speaks like:** [Concrete description]

**The system does not speak like:** [What to avoid]

**Vocabulary:**

| Use | Avoid | Reason |
|---|---|---|
| [Preferred term] | [Term to avoid] | [Why] |
| [Preferred term] | [Term to avoid] | [Why] |

### 3.2 Persona Adaptation

<!--
Define how the tone shifts based on the detected visitor profile.
The core voice stays consistent — the register adapts.
-->

| Persona | Register adjustment | Example difference |
|---|---|---|
| [Persona 1] | [How tone shifts] | [Concrete example] |
| [Persona 2] | [How tone shifts] | [Concrete example] |

### 3.3 What the System Never Does

<!--
Hard rules that apply regardless of persona or stage.
These are the lines that are never crossed.
-->

- [Hard rule 1 — e.g. "Never claims to be a human if asked directly"]
- [Hard rule 2]
- [Hard rule 3]

---

## 4. Dialogue Flows

<!--
Document the primary conversation flows the system must handle.
Each flow specifies:
- Trigger (what starts this flow)
- Happy path (the ideal conversation progression)
- Key decision points (where the system makes a choice)
- Exit (how the flow ends)

Include sample dialogues for each flow. These become QA test cases.
-->

### 4.1 [Flow name — e.g. "High-intent visitor, business hours"]

**Trigger:** [What initiates this flow]
**Personas:** [Which personas this flow applies to]
**Expected outcome:** [What success looks like for this flow]

**Sample dialogue:**

```
Visitor:  [Opening message]

System:   [Response — Stage 1: answer the question]

Visitor:  [Follow-up that reveals a qualification signal]

System:   [Response — Stage 2: answer + one qualifying question]
          [Note: system has now detected Problem fit]

Visitor:  [Response that adds another signal]

System:   [Response — Stage 2 continues]
          [Note: system has now detected Authority fit]

Visitor:  [Message with timing signal]

System:   [Response — Stage 3 triggered: propose next step]
          [Note: hot lead threshold reached]

Visitor:  [Accepts proposal]

System:   [Capture flow: collect email, confirm next steps]
```

**Decision points in this flow:**

| Point | Condition | System behaviour |
|---|---|---|
| [Point 1] | [What the system detects] | [What it does] |
| [Point 2] | [What the system detects] | [What it does] |

---

### 4.2 [Flow name — e.g. "Exploratory visitor, low intent"]

[Same structure]

---

### 4.3 [Flow name — e.g. "Explicit human request"]

[Same structure]

---

### 4.4 [Flow name — e.g. "Outside business hours"]

[Same structure]

---

### 4.5 [Flow name — e.g. "Negative persona — competitor"]

[Same structure]

---

## 5. Specific Conversation Patterns

<!--
Document the handling of specific question types or situations
that require a defined response pattern.
These are more granular than full flows — they are recurring
moments within conversations that need consistent handling.
-->

### 5.1 Pricing Questions

**Pattern:** Visitor asks about cost, rates, or pricing.

**Rule:** Never give specific numbers. Acknowledge the question honestly.
Explain why a number without scoping would not be useful. Offer a call
as the natural next step. Never sound evasive.

**Example:**
```
Visitor:  "How much does it cost to work with you?"

System:   "[Acknowledge + honest explanation + offer call]"
```

**Anti-pattern:**
```
// ❌ Evasive — damages trust
System: "Our pricing varies. Please contact us for more information."

// ❌ Premature close — too pushy
System: "I can't share pricing here. Book a call to find out."
```

---

### 5.2 [Pattern name — e.g. "Out of scope questions"]

[Same structure]

---

### 5.3 [Pattern name — e.g. "Existing client support requests"]

[Same structure]

---

### 5.4 [Pattern name — e.g. "Direct request for human"]

[Same structure]

---

### 5.5 [Pattern name — e.g. "Conversation stall"]

[Same structure]

---

## 6. Edge Cases

<!--
Document situations that fall outside the normal flows.
Each edge case needs:
- Trigger (what causes it)
- Why it is tricky (what makes it a design challenge)
- Required behaviour
- Example

Failure to document edge cases leads to undefined behaviour in production.
-->

| Edge case | Trigger | Required behaviour |
|---|---|---|
| [Case 1] | [What causes it] | [What the system does] |
| [Case 2] | [What causes it] | [What the system does] |

### [Edge case name — detailed]

**Trigger:** [What causes this situation]

**Why it is tricky:** [What makes this a design challenge]

**Required behaviour:** [What the system must do]

**Example:**
```
Visitor:  [Edge case message]
System:   [Correct response]
```

---

## 7. Prohibited Behaviours

<!--
Explicit list of things the system must never do.
These feed directly into the system prompt as hard constraints.
Group by category.
-->

### Content

- [The system never fabricates information not in its knowledge base]
- [The system never makes commitments the team cannot honour]
- [The system never reveals information about internal operations]

### Tone

- [The system never uses high-pressure sales language]
- [The system never dismisses a visitor's question]

### Process

- [The system never asks for contact information before providing value]
- [The system never escalates negative personas to the sales team]
- [The system never asks more than one qualifying question per exchange]

---

## 8. System Prompt Architecture

<!--
Define the structure of the system prompt — not its content,
but how it is organised and what each section does.
The actual prompt content is a separate artefact.

This section allows the team to reason about the prompt structure
independently of the specific wording.
-->

### 8.1 Prompt Layer Structure

| Layer | Purpose | Stable? | Example content |
|---|---|---|---|
| Role definition | Establishes who the system is | Yes | "You are a knowledgeable [company] representative..." |
| Conversation model | Stage rules, qualifying question limits | Yes | Stage 1/2/3 instructions |
| Persona instructions | Tone adaptation per detected persona | Yes | Per-persona register guidance |
| Prohibited behaviours | Hard constraints | Yes | Never reveal pricing, never fabricate |
| Knowledge scope | What the system knows and does not know | Yes | "Answer from retrieved context only" |
| Handoff instructions | When and how to escalate | Yes | Escalation trigger conditions |
| Context injection | Dynamic: retrieved RAG chunks, session state | No | [Injected at runtime] |

### 8.2 Context Window Budget

<!--
Define how the context window is allocated across components.
Total must not exceed the model's context limit.
This is a planning artefact — actual values are set in the TRD.
-->

| Component | Estimated tokens | Notes |
|---|---|---|
| System prompt (static) | [~N tokens] | Fixed per session |
| Retrieved RAG chunks | [~N tokens per turn] | Variable — capped by threshold |
| Conversation history | [~N tokens] | Sliding window — see TRD EC-13 |
| Current turn | [~N tokens] | Variable |
| **Total budget** | **[N tokens]** | Must be < model context limit |

---

## 9. QA Test Cases

<!--
Derived from the dialogue flows and edge cases above.
Each test case specifies the input, the expected behaviour,
and the failure condition.

These become the structured test suite referenced in the PRD DoD.
-->

| ID | Persona | Input | Expected behaviour | Failure condition |
|---|---|---|---|---|
| TC-001 | [Persona] | [Input message or scenario] | [What the system should do] | [What would make this test fail] |
| TC-002 | [Persona] | [Input] | [Expected] | [Failure] |

### Adversarial Test Cases

<!--
Inputs designed to probe failure modes:
- Attempts to extract sensitive information
- Attempts to break character
- Attempts to bypass qualification logic
- Edge cases in the conversation model
-->

| ID | Type | Input | Expected behaviour |
|---|---|---|---|
| TC-ADV-001 | [Type — e.g. competitor probe] | [Input] | [Expected] |
| TC-ADV-002 | [Type — e.g. prompt injection] | [Input] | [Expected] |

---

## 10. Revision History

| Version | Date | Author | Changes |
|---|---|---|---|
| 1.0 | YYYY-MM-DD | [Author] | Initial version |

---

*This Conversation Design Document is the authoritative specification for
[system name]'s conversational behaviour. Changes to conversation flows,
tone guidelines, or prohibited behaviours require a version increment and
review by the PM and AI Engineering Lead.*
