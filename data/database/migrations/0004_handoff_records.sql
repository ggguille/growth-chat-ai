CREATE TABLE IF NOT EXISTS handoff_records (
    session_id      TEXT        NOT NULL,
    triggered_at    TIMESTAMPTZ NOT NULL,
    lead_level      TEXT        NOT NULL CHECK (lead_level IN ('hot', 'warm', 'cold')),
    handoff_reason  TEXT        NOT NULL,
    visitor_email   TEXT,

    slack_status    TEXT        NOT NULL CHECK (slack_status IN ('ok', 'failed')),
    slack_attempts  INT         NOT NULL DEFAULT 0,
    slack_last_http INT,

    crm_status      TEXT        NOT NULL CHECK (crm_status IN ('ok', 'failed')),
    crm_attempts    INT         NOT NULL DEFAULT 0,
    crm_record_id   TEXT,
    crm_last_http   INT,

    fallback_sent   BOOLEAN     NOT NULL DEFAULT FALSE,
    outcome         TEXT        NOT NULL CHECK (outcome IN ('complete', 'partial_failure', 'total_failure')),
    completed_at    TIMESTAMPTZ NOT NULL,

    PRIMARY KEY (session_id, triggered_at)
);

CREATE INDEX IF NOT EXISTS handoff_records_outcome_idx
    ON handoff_records (outcome)
    WHERE outcome != 'complete';

CREATE INDEX IF NOT EXISTS handoff_records_triggered_at_idx
    ON handoff_records (triggered_at DESC);
