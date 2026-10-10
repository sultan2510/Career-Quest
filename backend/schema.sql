-- Run in the Supabase SQL editor. The API connects directly as the database user,
-- so RLS is enabled with no policies: the public Supabase REST API cannot read these tables.
create table if not exists users (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  email text not null unique,
  password_hash text not null,
  email_verified boolean not null default false,
  created_at timestamptz not null default now()
);
create table if not exists email_tokens (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  kind text not null check (kind in ('verify','reset')),
  token_hash text not null unique,
  expires_at timestamptz not null,
  created_at timestamptz not null default now()
);
create table if not exists progress (
  user_id uuid primary key references users(id) on delete cascade,
  data jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);
-- Anonymous progress is owned by an unguessable, HTTP-only guest cookie.
-- Only its SHA-256 hash is stored here; accounts continue to use progress.
create table if not exists guest_sessions (
  id uuid primary key default gen_random_uuid(),
  token_hash text not null unique,
  data jsonb not null default '{"v":1}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  expires_at timestamptz not null default (now() + interval '90 days')
);
create index if not exists guest_sessions_expires_at on guest_sessions(expires_at);
alter table users add column if not exists pending_guest_id uuid references guest_sessions(id) on delete set null;
alter table users enable row level security;
alter table email_tokens enable row level security;
alter table progress enable row level security;
alter table guest_sessions enable row level security;

-- RAG knowledge (filled by ingest.py) and login/RAG throttling
create table if not exists rag_chunks (
  id serial primary key, title text not null, content text not null,
  tsv tsvector generated always as (to_tsvector('english', title || ' ' || content)) stored
);
create index if not exists rag_chunks_tsv on rag_chunks using gin (tsv);
create table if not exists rate_limits (key text not null, at timestamptz not null default now());
create index if not exists rate_limits_key on rate_limits (key, at);
alter table rag_chunks enable row level security;
alter table rate_limits enable row level security;
