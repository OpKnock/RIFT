-- RIFT 005: owner scoping for run records.
-- The application writes user_id on experiment_runs when the caller asserts
-- one (see rift.auth.extract_user_id); without this column those inserts
-- fail. Additive + idempotent like all RIFT migrations.

alter table public.experiment_runs
  add column if not exists user_id uuid references auth.users(id) on delete set null;

create index if not exists experiment_runs_user_idx
  on public.experiment_runs(user_id, created_at desc);

comment on column public.experiment_runs.user_id is 'Asserted owner id for server-side ownership checks; full unforgeable tenancy requires Supabase Auth JWT verification in front of the API.';
