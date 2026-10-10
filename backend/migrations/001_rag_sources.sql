-- Add source identifiers without changing existing accounts, progress or chunks.
create table if not exists rag_chunks (
  id serial primary key,
  title text not null,
  content text not null,
  tsv tsvector generated always as (to_tsvector('english', title || ' ' || content)) stored
);
alter table rag_chunks add column if not exists source_key text;
alter table rag_chunks add column if not exists url text;
alter table rag_chunks add column if not exists kind text not null default 'knowledge';
alter table rag_chunks add column if not exists metadata jsonb not null default '{}'::jsonb;
create unique index if not exists rag_chunks_source_key on rag_chunks (source_key);
create index if not exists rag_chunks_tsv on rag_chunks using gin (tsv);
alter table rag_chunks enable row level security;
