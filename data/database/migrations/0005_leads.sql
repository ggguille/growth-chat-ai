-- No FK to LangGraph checkpointer tables — those are created separately by
-- AsyncPostgresSaver.setup() at backend startup. Linkage is via session_id value.
CREATE TABLE IF NOT EXISTS leads (
    id                   SERIAL      PRIMARY KEY,
    session_id           TEXT        NOT NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),

    lead_level           TEXT        NOT NULL CHECK (lead_level IN ('hot', 'warm', 'cold')),
    handoff_reason       TEXT        NOT NULL CHECK (handoff_reason IN ('hot_lead', 'explicit_request', 'stall', 'llm_failure')),

    visitor_email        TEXT,
    visitor_name         TEXT,
    visitor_company      TEXT,
    visitor_role         TEXT,

    problem_fit          TEXT        NOT NULL,
    authority_fit        TEXT        NOT NULL,
    company_fit          TEXT        NOT NULL,
    timing_fit           TEXT        NOT NULL,
    is_consultant        BOOLEAN     NOT NULL DEFAULT FALSE,
    referral_mentioned   BOOLEAN     NOT NULL DEFAULT FALSE,

    turn_count           INTEGER     NOT NULL,
    signals_observed     JSONB       NOT NULL DEFAULT '[]',

    conversation_summary TEXT        NOT NULL
);

CREATE INDEX IF NOT EXISTS leads_created_at_idx  ON leads (created_at DESC);
CREATE INDEX IF NOT EXISTS leads_lead_level_idx  ON leads (lead_level);
CREATE INDEX IF NOT EXISTS leads_session_id_idx  ON leads (session_id);
