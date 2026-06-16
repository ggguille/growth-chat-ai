"""Layer 7: qualification state serialiser.

Produces the JSON block injected per turn to ground the LLM in current
session state (lead level, qualification signals, proposal history, etc.).
"""
from __future__ import annotations

import json

from backend.handoff.business_hours import is_business_hours
from backend.qualification.models import QualificationState


def format_qualification_state(state: dict) -> str:
    qual: QualificationState | None = state.get("qualification")
    if qual is None:
        qual = QualificationState()

    return json.dumps(
        {
            "qualification": {
                "problem_fit": qual.problem_fit,
                "authority_fit": qual.authority_fit,
                "company_fit": qual.company_fit,
                "timing_fit": qual.timing_fit,
                "is_negative_persona": qual.is_negative_persona,
                "is_no_fit": qual.is_no_fit,
            },
            "lead_level": state.get("lead_level", "cold"),
            "turn_counter": state.get("turn_counter", 0),
            "stage3_proposals_issued": state.get("stage3_proposals_issued", 0),
            "visitor_email": state.get("visitor_email") or None,
            "followup_commitment_sentence": (
                "One of our engineers will be in touch within a few hours."
                if is_business_hours(same_day_followup=True)
                else "They will reach out first thing next business morning before 10am CET/CEST."
            ),
            "is_consultant": state.get("is_consultant", False),
            "referral_mentioned": state.get("referral_mentioned", False),
            "explicit_human_request": state.get("explicit_human_request", False),
            "stage3_declined": state.get("stage3_declined", False),
        },
        indent=2,
    )
