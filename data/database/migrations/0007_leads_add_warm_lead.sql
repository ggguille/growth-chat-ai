ALTER TABLE leads DROP CONSTRAINT IF EXISTS leads_handoff_reason_check;
ALTER TABLE leads ADD CONSTRAINT leads_handoff_reason_check
    CHECK (handoff_reason IN ('hot_lead', 'warm_lead', 'explicit_request', 'stall', 'llm_failure'));
