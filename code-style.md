# Code Style

No formatter is enforced in CI — follow the existing style so the codebase stays uniform. When in doubt, match the neighboring file.

## Python

- **Runtime**: Python ≥ 3.11. Standard library first; every third-party import must be behind a `pyproject.toml` extra (`dev`, `supabase`, `qiskit`, `physio`).
- **Typing**: annotate all public function signatures (`dict`, `list[...]`, `X | None`). Keep `from __future__ import annotations` at the top of new modules.
- **Data**: immutable domain types as `@dataclass(frozen=True)`. New fields on shared models must be keyword-only (`kw_only=True`) so old positional construction fails loudly instead of silently shifting meaning.
- **Docstrings**: every public function gets one line stating what it does plus its failure contract. Document what is *not* done as well as what is (e.g. "tested against a local fixture, not a live server").
- **Errors**: fail closed. Validate inputs, raise `ValueError`/`FhirError` with a reason, never clamp, default, or invent data. Broad `except` blocks must log (`log_event` with `request_id`) and return a truthful status — never bare `pass` (Bandit `B110` fails the build; justified suppressions carry `# nosec` + reason).
- **No `assert` for runtime validation** in `src/` — asserts are for tests only.
- **Determinism**: seeded RNGs, sorted outputs, no wall-clock time in IDs or hashes. Timestamps come from data, never `now()`, except explicit provenance metadata.
- **Secrets**: server-side only, from env via `settings.py`. Error bodies carry `{error, request_id}` — never tracebacks, keys, or tokens.
- **Naming**: modules `snake_case`, tests `test_<area>_<behavior>.py`, Guardian rules `G-NNN`, env vars `RIFT_*` (canonical; legacy fallbacks documented in `.env.example`).

## Tests

- `pytest`, one behavior per test, deterministic (seeded, no network except explicitly-marked integration tests).
- Every bug fix ships with a regression test proving the failure mode — preferably one that fails before the fix.
- Audit invariants live in `tests/test_internal_audit_regression.py`.

## Shell / YAML / JSON / SQL

- Shell examples target POSIX `sh`; PowerShell notes go inline where needed. Never use `head`/`tail`/`grep` in portable instructions without noting they are Unix-only.
- YAML (workflows, K8s, Prometheus): 2-space indent; validate with `python -c "import yaml..."` before committing.
- SQL migrations: additive + idempotent only (`IF NOT EXISTS`, guarded constraints), RLS-safe. See `database.md`.

## Commits

- Small, single-purpose commits: `<area>: <what + test count>` (e.g. `Fix webhook resume on unique-violation; 219 tests green`).
- Never commit secrets, generated artifacts, debug scripts, or `__pycache__`. Scratch tooling belongs in `scripts/archive/` with a README note, not repo root.
