# rift.routes — HTTP route handlers (split from rift.api)

`src/rift/api.py` (`Handler`, stdlib `BaseHTTPRequestHandler`) owns the HTTP
boundary: parsing, rate limiting, auth, dispatch, and the 404 tail. The 55
`if path == ...` route blocks used to live inline in `do_GET`/`do_POST`,
making `api.py` ~2900 lines. They now live here, one module per area:

| module               | routes                                                        |
|----------------------|---------------------------------------------------------------|
| `routes_core`        | `/api/health`, `/api/meta`, `/api/demo`, `/api/events/stream`, `/metrics`, `/api/persistence/status`, `/app/*` |
| `routes_auth`        | `/api/auth/session`, `/api/auth/logout`, `/api/auth/session-info` |
| `routes_billing`     | `/api/billing/status`, `/api/billing/entitlement`, `/api/billing/checkout`, `/api/billing/webhook` |
| `routes_experiments` | `/api/experiments…`, `/api/runs…` (22 routes: CRUD, runs, execute, versions, compare, import, scheduler, …) |
| `routes_operations`  | `/api/operations/incidents…`, `/api/operations/decisions…`    |
| `routes_twin`        | `/api/twin/…`, `/api/explainability/…`, `/api/intelligence/…` |
| `support`            | shared module-level helpers/constants (single home)           |

## Calling convention

Each handler has the shape:

```python
def get_api_demo(h, request_id, timer, path, query):
    """Route if path == "/api/demo": (moved verbatim from api.py do_GET)."""
    ...
    return True   # handled: stop dispatching
    ...
    return False  # shape-guard miss: let the next route try
```

`h` is the `Handler` instance (`self` renamed — code tokens only, string
literals byte-identical). `do_GET`/`do_POST` in `api.py` keep their preamble
(request id, timer, path/query parsing, rate limit) and 404 tail, and
dispatch in the original order:

```python
if path == "/api/demo":
    if routes_core.get_api_demo(self, request_id, timer, path, query):
        return
```

A bare `return` in the original means "handled" → `return True`.
Fall-through (shape-guard miss) → trailing `return False`.

One deliberate fix during the split: the original `do_POST` never parsed
the query string, so the dispatch argument `query` would have been undefined.
No POST route reads `query` (verified), so defining
`query = parse_qs(parsed.query)` in the preamble — mirroring `do_GET` — is
behavior-preserving.

## Compatibility

`rift.api` re-exports every moved name
(`from .routes.support import ...`), so `rift.api.X` keeps working for
tests and readers. The single home for mutable state (e.g.
`_SEEN_WEBHOOK_KEYS`) is `rift.routes.support`; `rift.api` holds a
re-exported reference to the same object.

`FRONTEND_DIST` is anchored one level deeper here (`parents[3]` instead of
`parents[2]`) so it resolves to the identical directory; verified equal at
split time.

## Provenance

Generated mechanically by `split_api.py` (since removed), which aborts
loudly unless: route count is exactly 36 GET + 19 POST, every free name maps
to an explicit import, top-level returns are bool-only, string literals are
byte-identical, and no `self` NAME token remains. Verified by the full test
suite (`297 passed`) plus a live 15-endpoint smoke test.
