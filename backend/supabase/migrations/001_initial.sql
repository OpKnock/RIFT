create table if not exists public.experiments (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  name text not null,
  description text,
  scenario jsonb not null,
  causal_graph jsonb,
  status text not null default 'created',
  created_at timestamptz not null default now()
);
create table if not exists public.experiment_runs (
  id uuid primary key default gen_random_uuid(),
  experiment_id uuid not null references public.experiments(id) on delete cascade,
  seed bigint,
  optimizer text not null,
  result jsonb,
  metrics jsonb,
  created_at timestamptz not null default now()
);
create index if not exists experiment_runs_experiment_id_idx on public.experiment_runs(experiment_id);
alter table public.experiments enable row level security;
alter table public.experiment_runs enable row level security;
drop policy if exists "users can manage their experiments" on public.experiments;
drop policy if exists "users can manage runs for their experiments" on public.experiment_runs;
create policy "users can manage their experiments" on public.experiments for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "users can manage runs for their experiments" on public.experiment_runs for all using (exists (select 1 from public.experiments e where e.id = experiment_id and e.user_id = auth.uid())) with check (exists (select 1 from public.experiments e where e.id = experiment_id and e.user_id = auth.uid()));