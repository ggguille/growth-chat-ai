ALTER TABLE knowledge_chunks
    DROP COLUMN IF EXISTS proactive_eligible,
    DROP COLUMN IF EXISTS description,
    DROP COLUMN IF EXISTS title,
    DROP COLUMN IF EXISTS category;

ALTER TABLE knowledge_chunks_dev
    DROP COLUMN IF EXISTS proactive_eligible,
    DROP COLUMN IF EXISTS description,
    DROP COLUMN IF EXISTS title,
    DROP COLUMN IF EXISTS category;
