-- RAG vector store schema for Klikk Planning Agent
-- Run once against klikk_bi_etl:
--   psql -h 192.168.1.235 -U klikk_user -d klikk_bi_etl -f rag/schema.sql

CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA IF NOT EXISTS agent_rag;

CREATE TABLE IF NOT EXISTS agent_rag.documents (
    id          SERIAL PRIMARY KEY,
    doc_id      TEXT NOT NULL,       -- stable unique identifier per chunk
    source_path TEXT NOT NULL,       -- file path or 'tm1_api::<type>::<name>'
    doc_type    TEXT NOT NULL,       -- instruction | model_state | cube_rule | process_code | dimension_structure
    title       TEXT NOT NULL,
    content     TEXT NOT NULL,
    embedding   vector(512),         -- voyage-3-lite: 512 dimensions
    metadata    JSONB NOT NULL DEFAULT '{}',
    indexed_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(doc_id)
);

-- IVFFlat index for fast cosine similarity search (lists=50 for ~150 chunks)
CREATE INDEX IF NOT EXISTS idx_agent_rag_embedding
    ON agent_rag.documents
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 50);

CREATE INDEX IF NOT EXISTS idx_agent_rag_doc_type
    ON agent_rag.documents (doc_type);

CREATE INDEX IF NOT EXISTS idx_agent_rag_source
    ON agent_rag.documents (source_path);
