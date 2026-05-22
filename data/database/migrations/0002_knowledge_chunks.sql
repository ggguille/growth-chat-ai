CREATE TABLE IF NOT EXISTS knowledge_chunks (
    chunk_id      TEXT         PRIMARY KEY,
    source        TEXT         NOT NULL,
    chunk_index   INT          NOT NULL,
    content       TEXT         NOT NULL,
    content_hash  TEXT         NOT NULL,
    embedding     VECTOR(1536) NOT NULL,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    UNIQUE (source, chunk_index)
);

CREATE INDEX IF NOT EXISTS knowledge_chunks_embedding_idx
    ON knowledge_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
