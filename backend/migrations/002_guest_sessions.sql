-- Safe additive migration for databases initialized before guest persistence.
create table if not exists public.guest_sessions (
  id uuid primary key default gen_random_uuid(),
  token_hash text not null unique,
  data jsonb not null default '{"v":1}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  expires_at timestamptz not null default (now() + interval '90 days')
);
create index if not exists guest_sessions_expires_at on public.guest_sessions(expires_at);
alter table public.users add column if not exists pending_guest_id uuid references public.guest_sessions(id) on delete set null;
alter table public.guest_sessions enable row level security;
