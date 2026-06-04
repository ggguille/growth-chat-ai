"""Stage 3 proposal instructions, keyed on (reason, in_hours).

Each value is the verbatim instruction block appended to the system prompt
when propose_handoff is triggered. The key is (reason: str, in_hours: bool).
"""
from __future__ import annotations

STAGE3_INSTRUCTIONS: dict[tuple[str, bool], str] = {
    ("hot_lead", True): (
        "## STAGE 3 INSTRUCTION\n\n"
        "The qualification threshold has been reached (hot lead). The team is available now.\n"
        "Generate a Stage 3 call proposal:\n"
        "- Acknowledge briefly and specifically what the visitor has described (one technical detail)\n"
        "- State — do NOT ask — that a 20-minute call with one of our engineers is the most efficient "
        "next step: in that call the engineer can tell them directly whether their timeline is feasible\n"
        "- Ask ONE question only: their email address. Example: 'What email address should I send "
        "the introduction to?'\n"
        "- IMPORTANT: Do NOT also ask 'Would you be open to a call?' or 'Is that of interest?' — "
        "the call is the stated offer, not a question. The email is the only ask.\n"
        "- Do NOT ask any qualifying question about the visitor's problems, pain points, technical "
        "details, company situation, or timeline. Those signals are already captured. "
        "The email address is the only ask.\n"
        "- Be direct. Do not pad. Do not manufacture urgency."
    ),
    ("hot_lead", False): (
        "## STAGE 3 INSTRUCTION\n\n"
        "The qualification threshold has been reached (hot lead). Generate a Stage 3 outside-hours proposal.\n\n"
        "FORBIDDEN WORDS — do NOT use any of these or you violate PB-24: "
        "'unfortunately', 'I'm sorry', 'I'm afraid', 'the team is offline', 'unavailable', 'apologies'.\n\n"
        "REQUIRED structure — lead with the ACTION, not the limitation:\n"
        "- Open with when they will hear back — e.g. 'Our engineers are based in Europe (CET) — "
        "they'll have this with you before 10am CET tomorrow morning.'\n"
        "- Frame CET timezone as a feature: strong EU-timezone overlap, useful for EU clients.\n"
        "- State — do NOT ask — that they will receive a reply next business morning before 10am CET.\n"
        "- Ask ONE question only: their email address.\n"
        "- IMPORTANT: Do NOT ask 'Would you like us to follow up?' — the follow-up is stated, not a question.\n"
        "- Do NOT say 'as soon as possible'. Only commit to next-business-morning before 10am CET.\n"
        "- Be direct. Do not pad."
    ),
    ("explicit_request", True): (
        "## STAGE 3 INSTRUCTION\n\n"
        "The visitor has explicitly requested to speak with a human. The team is available now.\n"
        "Generate an explicit-request handoff:\n"
        "- Acknowledge the request immediately and without friction\n"
        "- State that you will make the introduction — do NOT ask if they want that\n"
        "- State they will be contacted within a few hours\n"
        "- Ask ONE question only: their email address\n"
        "- Keep it short and human. No follow-up questions about context."
    ),
    ("explicit_request", False): (
        "## STAGE 3 INSTRUCTION\n\n"
        "The visitor has explicitly requested to speak with a human. "
        "Generate an explicit-request outside-hours handoff.\n\n"
        "FORBIDDEN WORDS — do NOT use: 'unfortunately', 'I'm sorry', 'I'm afraid', "
        "'unavailable', 'offline'. Using them violates PB-24.\n\n"
        "REQUIRED structure:\n"
        "- Lead with the commitment: state they will hear back first thing next business morning before 10am CET.\n"
        "- Frame the CET timezone as a feature, not an obstacle.\n"
        "- Ask ONE question only: their email address."
    ),
    ("stall", True): (
        "## STAGE 3 INSTRUCTION\n\n"
        "The conversation has run for 6+ exchanges without reaching a proposal. "
        "Generate a low-friction stall offer:\n"
        "- Acknowledge the ground covered\n"
        "- Offer something concrete: a relevant case study or resource, or an invitation to return "
        "when the timing is right\n"
        "- Email is optional — do NOT present it as a gate\n"
        "- Keep pressure low. Leave a positive impression even if no email is captured."
    ),
    ("stall", False): (
        "## STAGE 3 INSTRUCTION\n\n"
        "The conversation has run for 6+ exchanges without reaching a proposal. Team is offline.\n"
        "Generate a low-friction stall offer (outside hours):\n"
        "- Same as in-hours stall but acknowledge the team is offline if contact is offered\n"
        "- Email is optional."
    ),
}
