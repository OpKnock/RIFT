-- RIFT billing boundary: Lemon Squeezy customer/subscription mirror + webhook audit log.
-- The simulation core never depends on these tables. They are only written by
-- server-side billing endpoints when Lemon Squeezy credentials are configured.
-- No products, prices, or credentials are stored here.

create table if not exists public.billing_customers (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete set null,
  lemon_customer_id text unique,
  email text,
  created_at timestamptz not null default now()
);

create table if not exists public.billing_subscriptions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete set null,
  lemon_subscription_id text unique not null,
  lemon_customer_id text,
  status text not null default 'unknown',
  variant_id text,
  renews_at timestamptz,
  ends_at timestamptz,
  raw jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.billing_events (
  id uuid primary key default gen_random_uuid(),
  event_name text not null,
  supported boolean not null default true,
  lemon_customer_id text,
  lemon_subscription_id text,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists billing_subscriptions_user_idx
  on public.billing_subscriptions(user_id, created_at desc);
create index if not exists billing_events_name_idx
  on public.billing_events(event_name, created_at desc);

alter table public.billing_customers enable row level security;
alter table public.billing_subscriptions enable row level security;
alter table public.billing_events enable row level security;

-- No grants to anon/authenticated: billing tables are service-role only.
-- Reads for a signed-in user should go through a server endpoint that
-- enforces ownership, never direct table access.
revoke all on table public.billing_customers from anon, authenticated;
revoke all on table public.billing_subscriptions from anon, authenticated;
revoke all on table public.billing_events from anon, authenticated;

comment on table public.billing_customers is 'Server-side Lemon Squeezy customer mirror. Service-role writes only.';
comment on table public.billing_subscriptions is 'Server-side subscription state mirror. Service-role writes only.';
comment on table public.billing_events is 'Webhook audit log for Lemon Squeezy events. Never store API keys here.';
