-- Dev-only table (384-dim, HuggingFace all-MiniLM-L6-v2).
-- Created in all environments; selected at runtime via KNOWLEDGE_TABLE_NAME=knowledge_chunks_dev.
CREATE TABLE IF NOT EXISTS knowledge_chunks_dev (
    chunk_id      TEXT        PRIMARY KEY,
    source        TEXT        NOT NULL,
    chunk_index   INT         NOT NULL,
    content       TEXT        NOT NULL,
    content_hash  TEXT        NOT NULL,
    embedding     VECTOR(384) NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (source, chunk_index)
);

CREATE INDEX IF NOT EXISTS knowledge_chunks_dev_embedding_idx
    ON knowledge_chunks_dev
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
