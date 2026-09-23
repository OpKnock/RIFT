# Deploy RIFT (v0.6.0 lab server)

## Local
```bash
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
python -m rift.cli demo
python -m rift.cli serve --port 8080
curl http://127.0.0.1:8080/api/health
```

## Docker
```bash
docker build -t rift:0.6.0 .
docker run --rm -p 8080:8080 \
  -e RIFT_SUPABASE_URL= -e RIFT_SUPABASE_KEY= \
  -e RIFT_API_TOKEN= -e RIFT_LEMON_SQUEEZY_WEBHOOK_SECRET= \
  rift:0.6.0
```
Image runs as non-root, stdlib-only runtime (extras installed only when needed).

## Production edge checklist
- Terminate TLS at the edge; the app server speaks plain HTTP.
- Set explicit CORS/rate limits at the edge (especially `/api/demo`, `/api/billing/webhook`).
- Inject secrets via vault/env, never build-args or images. Required for persistence: `RIFT_SUPABASE_URL` + `RIFT_SUPABASE_KEY`. For gated mode: `RIFT_API_TOKEN`. For billing: `RIFT_LEMON_SQUEEZY_*`.
- Apply Supabase migrations `001→004` in order (`supabase db push` or SQL editor).
- Point Lemon Squeezy webhooks at `https://<host>/api/billing/webhook` with the signing secret configured.
- Verify: `/api/health`, `/api/meta`, version scripts, and the release checklist.

## What this image is not
A certified safety system. See README safety boundary: no autonomous control of real emergency infrastructure.
