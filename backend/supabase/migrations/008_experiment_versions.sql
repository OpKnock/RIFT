-- RIFT 008: durable experiment version history.
-- Versions were archive-local (lost on restart for Supabase-backed
-- experiments). This adds a versions column so POST .../versions can
-- write through to the authoritative store; the in-process archive
-- remains a best-effort mirror. Additive + idempotent.
alter table public.experiments
  add column if not exists versions jsonb not null default '[]'::jsonb;
