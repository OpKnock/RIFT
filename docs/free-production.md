# Free-Tier Production Alternatives (documented 2026-09-26)

## 1. Local full stack (Docker Compose, zero cost)

```bash
# One-time: set required env vars
export RIFT_SUPABASE_URL=https://your-project.supabase.co
export RIFT_SUPABASE_KEY=your-service-role-key
export RIFT_API_TOKEN=$(openssl rand -hex 32)
export RIFT_SUPABASE_JWT_SECRET=$(openssl rand -hex 32)

# Start
docker compose -f deployment/docker/docker-compose.yml up -d
```

Services: RIFT API (prod image), Prometheus, Alertmanager, Grafana (preloaded dashboards).

Cost: $0 (local Docker). Requirements: Docker + 4 GB RAM.

## 2. Fly.io free allowance (3 shared-cpu-1x VMs, 160 GB-mo bandwidth)

```bash
fly launch --no-deploy --name rift-twin --region iad
fly secrets set RIFT_SUPABASE_URL=... RIFT_SUPABASE_KEY=... RIFT_API_TOKEN=... RIFT_SUPABASE_JWT_SECRET=...
fly deploy
```

The `deployment/docker/Dockerfile` is production-ready (non-root, healthcheck, constraints-pinned). `fly.toml` auto-generated; edit `services[0].internal_port=8080`.

## 3. Railway free tier (500h/mo, shared CPU, 1 GB RAM)

```bash
railway login
railway init
railway add --service rift-api
railway variables set RIFT_SUPABASE_URL=... RIFT_SUPABASE_KEY=... RIFT_API_TOKEN=... RIFT_SUPABASE_JWT_SECRET=...
railway up
```

Auto-detects the `Dockerfile` at repo root.

## 4. Render free tier (750h/mo, spins down after inactivity)

Connect GitHub repo → Web Service → Docker → `deployment/docker/Dockerfile` → set env vars → deploy.

## 5. Vercel (serverless, 100 GB-hours/mo) — NOT SUITABLE

RIFT needs persistent HTTP server + websockets; Vercel Edge Functions are 30s max, no persistent state.

## Current status

- `deployment/docker/Dockerfile`: production-hardened, builds in CI, smoke-tested.
- `deployment/docker/docker-compose.yml`: full stack with monitoring.
- `deployment/kubernetes/*.yaml`: K8s manifests (JWT secret required, rate limit, HPA/PDB).
- Free-tier hosting: **Fly.io or Railway recommended** — both run the exact same Docker image locally and in cloud.

## Next step (requires your account)

Pick one: `fly auth login` → `fly launch` OR `railway login` → `railway init` → deploy. I can drive the CLI if you run the auth.