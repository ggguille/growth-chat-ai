---
description: "Competitor conducting intelligence gathering — should not be escalated to sales."
---

# N1 — The Competitor

> *"I want to understand how the company positions itself, what they charge, and how they talk about their methodology."*

## Profile

| Field | Detail |
| --- | --- |
| **Role** | BD, sales, product, or strategy roles at competing firms |
| **Company type** | Nearshore software vendor, AI consultancy, staff augmentation provider |
| **Intent** | Competitive intelligence gathering |
| **Detectability** | Low — will not self-identify |

## Behaviour patterns

- Asks detailed questions about internal methodology, pricing, or team structure.
- Questions lack a concrete problem to solve — they are probing, not seeking solutions.
- May claim to be a potential client but ask unusually specific operational questions.
- Often asks about technology stack, delivery process, or how the company structures contracts.

## Risk to the company

- Extraction of pricing signals, positioning language, or methodology details.
- Intelligence on which clients or verticals the company is targeting.
- Using the chat to benchmark against the company's sales scripts.

## Detection signals

- Questions are about the company's operations, not the visitor's problem.
- No mention of a specific initiative, company, or role.
- Asks multiple questions in quick succession without providing context.
- Questions about pricing presented as hypotheticals ("say a company wanted to...").

## Chat strategy

The chat cannot reliably identify competitors, so the strategy is defensive by design:

- Never reveal information beyond what is already public on the website.
- Respond to pricing questions with the standard answer ("we scope based on the specific initiative — happy to discuss on a call").
- Do not escalate to the sales team unless the visitor provides credible context (company name, specific initiative, contact details).
- Treat unverifiable high-specificity questions as a signal to de-escalate rather than engage deeper.

## What not to do

Do not build a "competitor detection" feature that tries to identify and block specific companies — it will generate false positives on real leads and create a poor experience. The right approach is a chat that is confidently helpful on public information and naturally non-committal on anything sensitive.
