-- RIFT 006: model registry + prediction audit trail.
-- Supports traceable, versioned predictions: every prediction references a
-- registered model version, and audit rows carry the verification material
-- (input hash, weights digest, Guardian verdict) needed to answer "why did
-- RIFT produce this?" months later. Additive + idempotent. Service-role
-- writes only; reads go through server endpoints that enforce ownership.

create table if not exists public.model_registry (
  model_id text primary key,
  target text not null,
  threshold double precision not null,
  weights_digest text,
  dataset_versions jsonb not null default '[]'::jsonb,
  schema_version text not null default 'patient-state-v1',
  calibration jsonb not null default '{}'::jsonb,
  status text not null default 'research',
  deployment_gate text not null default 'closed',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.prediction_audit (
  id uuid primary key default gen_random_uuid(),
  prediction_id text unique not null,
  user_id uuid references auth.users(id) on delete set null,
  experiment_id uuid references public.experiments(id) on delete set null,
  model_id text not null references public.model_registry(model_id),
  weights_digest text,
  input_hash text,
  result jsonb not null default '{}'::jsonb,
  guardian_passed boolean,
  created_at timestamptz not null default now()
);

create index if not exists prediction_audit_user_idx
  on public.prediction_audit(user_id, created_at desc);
create index if not exists prediction_audit_model_idx
  on public.prediction_audit(model_id, created_at desc);
create index if not exists prediction_audit_prediction_idx
  on public.prediction_audit(prediction_id);

alter table public.model_registry enable row level security;
alter table public.prediction_audit enable row level security;

revoke all on table public.model_registry from anon, authenticated;
revoke all on table public.prediction_audit from anon, authenticated;

drop trigger if exists model_registry_touch_updated_at on public.model_registry;
create trigger model_registry_touch_updated_at
  before update on public.model_registry
  for each row execute function public.rift_touch_updated_at();

comment on table public.model_registry is 'Versioned model records. Service-role writes only; status transitions require evidence.';
comment on table public.prediction_audit is 'Deterministic prediction audit trail keyed by prediction_id. Never store secrets or raw credentials here.';
