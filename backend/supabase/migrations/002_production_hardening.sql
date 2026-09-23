-- RIFT production hardening: explicit grants and metadata for reproducible experiments.
revoke all on table public.experiments from anon, authenticated;
revoke all on table public.experiment_runs from anon, authenticated;
grant select, insert, update, delete on public.experiments to authenticated;
grant select, insert, update, delete on public.experiment_runs to authenticated;

alter table public.experiments
  add column if not exists metadata jsonb not null default '{}'::jsonb;

alter table public.experiment_runs
  add column if not exists duration_ms double precision,
  add column if not exists constraint_violations integer not null default 0;

create index if not exists experiments_user_created_idx
  on public.experiments(user_id, created_at desc);

create index if not exists experiment_runs_created_idx
  on public.experiment_runs(experiment_id, created_at desc);

comment on column public.experiments.metadata is 'UI/client metadata; never store secrets here.';
comment on column public.experiment_runs.result is 'Serialized reproducible engine result.';
