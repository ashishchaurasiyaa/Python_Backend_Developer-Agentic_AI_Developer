-- Runs once when the Postgres container first initializes its data dir.
-- Enables pgvector so `vector` columns work (used by the chunks table on Day 2).
CREATE EXTENSION IF NOT EXISTS vector;
