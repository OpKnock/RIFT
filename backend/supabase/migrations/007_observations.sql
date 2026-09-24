-- RIFT 007: observation + revision persistence for the v1 data platform.
--
-- Canonical observations are immutable events keyed by content hash
-- (observation_id); corrections arrive as new revision rows that supersede
-- without mutating history. Service-role writes only; reads go through
-- server endpoints that enforce ownership. Additive + idempotent.
create table if not exists public.observations (
  observation_id text primary key,
  batch_id text,
  user_id uuid references auth.users(id) on delete set null,
  patient_id text not null,
  observed_at timestamptz not null,
  source text not null,
  metric text not null,
  value double precision not null,
  unit text not null,
  quality double precision not null default 1.0,
  provenance jsonb not null default '{}'::jsonb,
  terminology jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.observation_revisions (
  revision_id text primary key,
  supersedes_id text not null references public.observations(observation_id),
  observation_id text not null references public.observations(observation_id),
  reason text not null,
  revised_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create index if not exists observations_patient_time_idx
  on public.observations(patient_id, observed_at);
create index if not exists observations_batch_idx
  on public.observations(batch_id);
create index if not exists observation_revisions_supersedes_idx
  on public.observation_revisions(supersedes_id);

alter table public.observations enable row level security;
alter table public.observation_revisions enable row level security;

revoke all on table public.observations from anon, authenticated;
revoke all on table public.observation_revisions from anon, authenticated;

comment on table public.observations is 'Immutable canonical observation events keyed by content hash. Service-role writes only.';
comment on table public.observation_revisions is 'Correction records that supersede without mutating history.';
