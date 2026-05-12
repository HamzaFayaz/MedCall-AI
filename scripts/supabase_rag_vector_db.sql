-- Supabase RAG Vector DB setup
-- Purpose: Create the pgvector-backed knowledge chunk table and search RPC.
-- This file is separate from scripts/supabase_setup.sql, which owns the
-- structured EHR-style tables for doctors, patients, profiles, and appointments.

-- Enable required extensions.
create extension if not exists vector with schema extensions;
create extension if not exists pgcrypto with schema extensions;

-- Store one row per approved RAG knowledge chunk.
-- Embedding dimension is 1024 for Qwen/Qwen3-Embedding-0.6B.
create table if not exists public.knowledge_chunks (
    id uuid primary key default gen_random_uuid(),
    content text not null,
    source_file text not null,
    source_type text not null,
    section text not null,
    topic text,
    department text,
    allowed_claims text[] not null default '{}',
    metadata jsonb not null default '{}'::jsonb,
    kb_version text not null default 'kb_v1',
    embedding vector(1024) not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint knowledge_chunks_source_section_version_key unique (
        source_file,
        section,
        kb_version
    )
);

-- Keep common metadata filters fast before vector ranking.
create index if not exists knowledge_chunks_kb_version_idx
    on public.knowledge_chunks (kb_version);

create index if not exists knowledge_chunks_source_type_idx
    on public.knowledge_chunks (source_type);

create index if not exists knowledge_chunks_department_idx
    on public.knowledge_chunks (department)
    where department is not null;

-- HNSW is a good default for pgvector cosine search and does not need a
-- training step before inserts.
create index if not exists knowledge_chunks_embedding_hnsw_idx
    on public.knowledge_chunks
    using hnsw (embedding vector_cosine_ops);

-- Server-side retrieval function used by the RAG vector DB adapter.
-- Returns chunks ranked by cosine similarity, with optional scope filters.
create or replace function public.match_knowledge_chunks(
    query_embedding vector(1024),
    match_count int default 4,
    filter_kb_version text default 'kb_v1',
    filter_source_type text default null,
    filter_topic text default null,
    filter_department text default null
)
returns table (
    id uuid,
    content text,
    source_file text,
    source_type text,
    section text,
    topic text,
    department text,
    allowed_claims text[],
    metadata jsonb,
    kb_version text,
    score double precision
)
language plpgsql
stable
as $$
begin
    return query
    select
        kc.id,
        kc.content,
        kc.source_file,
        kc.source_type,
        kc.section,
        kc.topic,
        kc.department,
        kc.allowed_claims,
        kc.metadata,
        kc.kb_version,
        1 - (kc.embedding <=> query_embedding) as score
    from public.knowledge_chunks kc
    where kc.kb_version = filter_kb_version
      and (filter_source_type is null or kc.source_type = filter_source_type)
      and (filter_topic is null or kc.topic = filter_topic)
      and (filter_department is null or kc.department = filter_department)
    order by kc.embedding <=> query_embedding
    limit greatest(match_count, 1);
end;
$$;

-- RAG chunks should be read through the backend/service-role path, not directly
-- from untrusted clients.
alter table public.knowledge_chunks enable row level security;
