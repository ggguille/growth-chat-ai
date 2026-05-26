ALTER TABLE knowledge_chunks
    ADD COLUMN IF NOT EXISTS category           TEXT    NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS title              TEXT    NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS description        TEXT    NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS proactive_eligible BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE knowledge_chunks_dev
    ADD COLUMN IF NOT EXISTS category           TEXT    NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS title              TEXT    NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS description        TEXT    NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS proactive_eligible BOOLEAN NOT NULL DEFAULT false;
