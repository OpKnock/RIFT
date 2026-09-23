-- RIFT 004: first-class experiment model.
-- Adds durable identity fields (ownership, lifecycle, reproducibility) without
-- breaking existing rows. All changes are additive + idempotent.

-- Experiments: lifecycle + reproducibility + ownership/project scoping.
alter table public.experiments
  add column if not exists user_id uuid references auth.users(id) on delete cascade,
  add column if not exists project_id uuid,
  add column if not exists perturbations jsonb not null default '[]'::jsonb,
  add column if not exists policy_variables jsonb not null default '[]'::jsonb,
  add column if not exists optimizer_config jsonb not null default '{}'::jsonb,
  add column if not exists backend text not null default 'statevector-simulator',
  add column if not exists seed bigint,
  add column if not exists engine_version text not null default '0.6.0',
  add column if not exists error jsonb,
  add column if not exists fingerprint text,
  add column if not exists updated_at timestamptz not null default now();

-- Constrain lifecycle status to the documented set (allow legacy 'created').
do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'experiments_status_check'
  ) then
    alter table public.experiments
      add constraint experiments_status_check
      check (status in ('created','configured','running','succeeded','failed'));
  end if;
end $$;

create index if not exists experiments_owner_updated_idx
  on public.experiments(user_id, updated_at desc);
create index if not exists experiments_fingerprint_idx
  on public.experiments(fingerprint);
create index if not exists experiments_project_idx
  on public.experiments(project_id, updated_at desc);

-- Runs: backend/config/version + duration/error + updated_at.
alter table public.experiment_runs
  add column if not exists backend text not null default 'statevector-simulator',
  add column if not exists optimizer_config jsonb not null default '{}'::jsonb,
  add column if not exists engine_version text not null default '0.6.0',
  add column if not exists error jsonb,
  add column if not exists fingerprint text,
  add column if not exists updated_at timestamptz not null default now();

create index if not exists experiment_runs_optimizer_idx
  on public.experiment_runs(optimizer, created_at desc);

-- updated_at triggers (create or replace safely).
create or replace function public.rift_touch_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;

drop trigger if exists experiments_touch_updated_at on public.experiments;
create trigger experiments_touch_updated_at
  before update on public.experiments
  for each row execute function public.rift_touch_updated_at();

drop trigger if exists experiment_runs_touch_updated_at on public.experiment_runs;
create trigger experiment_runs_touch_updated_at
  before update on public.experiment_runs
  for each row execute function public.rift_touch_updated_at();

drop trigger if exists billing_subscriptions_touch_updated_at on public.billing_subscriptions;
create trigger billing_subscriptions_touch_updated_at
  before update on public.billing_subscriptions
  for each row execute function public.rift_touch_updated_at();

-- Webhook idempotency: one row per provider event.
alter table public.billing_events
  add column if not exists provider_event_id text,
  add column if not exists idempotency_key text;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'billing_events_idempotency_key_unique'
  ) then
    alter table public.billing_events
      add constraint billing_events_idempotency_key_unique unique (idempotency_key);
  end if;
end $$;

create index if not exists billing_events_provider_idx
  on public.billing_events(provider_event_id, created_at desc);

comment on column public.experiments.fingerprint is 'Stable SHA-256 over canonical experiment spec; used for compare/reproduce.';
comment on column public.experiments.engine_version is 'Engine version that created the experiment; never trust cross-version results blindly.';
comment on column public.billing_events.idempotency_key is 'Dedup key for webhook retries; provider event id + name.';
