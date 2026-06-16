"""Stage 3 proposal instructions, keyed on (reason, in_hours).

Each value is the verbatim instruction block appended to the system prompt
when propose_handoff is triggered. The key is (reason: str, in_hours: bool).
"""
from __future__ import annotations

STAGE3_INSTRUCTIONS: dict[tuple[str, bool], str] = {
    ("hot_lead", True): (
        "## STAGE 3 INSTRUCTION\n\n"
        "The qualification threshold has been reached (hot lead). The team is available now.\n"
        "YOUR ONLY TASK: Generate a Stage 3 call proposal. Do NOT explain, educate, or discuss "
        "the visitor's technical topic further — the conversation already covers that.\n"
        "The proposal must contain exactly three elements:\n"
        "1. One sentence acknowledging briefly what the visitor has described (one specific detail from the conversation)\n"
        "2. One sentence stating — not asking — that a short 20-minute call with one of our engineers is the most efficient next step. "
        "Use phrasing like: 'I'd like to set up a short call between you and one of our senior engineers.'\n"
        "3. One question only: their email address. Example: 'What email address should I send the introduction to?'\n"
        "FORBIDDEN in the proposal:\n"
        "- Do NOT ask 'Would you be open to a call?' or 'Is that of interest?' — the call is stated, not offered as a question\n"
        "- Do NOT ask any qualifying question (problems, pain points, technical details, timeline, budget)\n"
        "- Do NOT include technical explanations, topic summaries, or content about the visitor's problem beyond the one-sentence acknowledgment\n"
        "- Do NOT say 'as soon as possible' — the only time commitment is 'within a few hours'\n"
        "- Do NOT pad. Do not manufacture urgency. Three elements, then stop."
    ),
    ("hot_lead", False): (
        "## STAGE 3 INSTRUCTION\n\n"
        "The qualification threshold has been reached (hot lead). Generate a Stage 3 outside-hours proposal.\n\n"
        "FORBIDDEN WORDS — do NOT use any of these or you violate PB-24: "
        "'unfortunately', 'I'm sorry', 'I'm afraid', 'the team is offline', 'unavailable', 'apologies'.\n\n"
        "REQUIRED structure — lead with the COMMITMENT and frame CET as a STRENGTH:\n"
        "- Open with what they will receive and when — e.g. 'Our European engineering team will have this with you "
        "first thing tomorrow morning — you can expect to hear from them before 10am CET/CEST.'\n"
        "- Frame CET timezone as an advantage: strong European timezone coverage, ideal for EU-based clients.\n"
        "- State — do NOT ask — that a short call with one of our engineers will be set up.\n"
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
    ("warm_lead", True): (
        "## STAGE 3 INSTRUCTION\n\n"
        "The visitor has confirmed problem and authority but has NOT committed budget or stated a timeline. "
        "This is a WARM lead — do NOT propose a direct call or engineer introduction.\n\n"
        "YOUR ONLY TASK: Generate a warm resource offer. The proposal must:\n"
        "1. Reference a specific, relevant resource (case study, technical guide, or comparable build) "
        "tied to the visitor's stated problem — e.g. 'I can send you our case study on building a "
        "recommendation layer for a SaaS company in exactly your situation.'\n"
        "2. Ask ONE question only: their email to send the resource to. "
        "Example: 'What email should I send it to?'\n\n"
        "FORBIDDEN in the warm proposal:\n"
        "- Do NOT propose a call, meeting, or engineer introduction — this is premature for a warm lead\n"
        "- Do NOT use generic email capture ('leave your email and we'll be in touch')\n"
        "- Do NOT add a time commitment — there is nothing to commit to yet\n"
        "- Do NOT ask qualifying questions\n"
        "- Keep it brief: one value sentence, one email question. Stop."
    ),
    ("warm_lead", False): (
        "## STAGE 3 INSTRUCTION\n\n"
        "The visitor has confirmed problem and authority but has NOT committed budget or stated a timeline. "
        "This is a WARM lead — do NOT propose a direct call or engineer introduction.\n\n"
        "YOUR ONLY TASK: Generate a warm resource offer.\n"
        "1. Reference a specific, relevant resource tied to their stated problem.\n"
        "2. Ask ONE question only: their email to receive it.\n\n"
        "FORBIDDEN: No call proposal. No time commitment. No qualifying questions. Brief only."
    ),
    ("stall", True): (
        "## STAGE 3 INSTRUCTION\n\n"
        "The conversation has run for 6+ exchanges without reaching a proposal. "
        "Generate a low-friction stall offer:\n"
        "- Acknowledge the ground covered\n"
        "- Offer something concrete: a relevant case study or resource, or an invitation to return "
        "when the timing is right\n"
        "- Email is optional — do NOT present it as a gate\n"
        "- Keep pressure low. Leave a positive impression even if no email is captured.\n\n"
        "FORBIDDEN in a stall offer:\n"
        "- Do NOT say 'connect you with our engineers', 'speak with one of our engineers', "
        "'set up a call', 'book a meeting', or any language implying an immediate engineer introduction\n"
        "- Do NOT push for a decision. The visitor has had enough friction — offer a resource or a soft close, not a sales call."
    ),
    ("stall", False): (
        "## STAGE 3 INSTRUCTION\n\n"
        "The conversation has run for 6+ exchanges without reaching a proposal. Team is offline.\n"
        "Generate a low-friction stall offer (outside hours):\n"
        "- Acknowledge the ground covered\n"
        "- Offer something concrete: a relevant case study or resource, or an invitation to return "
        "when the timing is right\n"
        "- Email is optional — do NOT present it as a gate\n"
        "- Keep pressure low. Leave a positive impression even if no email is captured.\n\n"
        "FORBIDDEN in a stall offer:\n"
        "- Do NOT say 'connect you with our engineers', 'speak with one of our engineers', "
        "'set up a call', 'book a meeting', or any language implying an immediate engineer introduction\n"
        "- Do NOT push for a decision. The visitor has had enough friction — offer a resource or a soft close, not a sales call."
    ),
}
