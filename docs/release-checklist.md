# Release checklist — RIFT v0.6.0 (release candidate)

- [ ] `pip install -e ".[dev]"` clean on Python 3.11
- [ ] `pytest` green (currently 146 tests)
- [ ] `python scripts/validate_migrations.py` ok (001→006 in order, RLS on)
- [ ] `python scripts/secret_scan.py` ok
- [ ] `python scripts/check_versions.py` ok (pyproject ↔ package ↔ health)
- [ ] `python -m rift.cli demo` prints futures + Guardian-ready candidates
- [ ] `python -m rift.cli serve` boots; `GET /api/health` → `status: ok`
- [ ] `GET /api/meta` lists capabilities/limits matching `docs/api.md`
- [ ] Migrations applied to staging Supabase in order; RLS verified per user
- [ ] Persistence smoke (staging): create → get → run → list with `user_id` scoping
- [ ] Billing smoke (only if credentials exist): checkout 201 + webhook 200 + duplicate replay flag + entitlement mapping
- [ ] Frontend smoke: twin sync, FORESIGHT trajectories, Guardian verdict, evidence panel render; 503/401/422 states shown honestly
- [ ] `CHANGELOG.md` entry matches this commit; version stays `0.6.0` (not 1.0)
- [ ] GitHub Actions `test` + `validate` + `security` jobs green on the release commit

Do not declare PRODUCTION READY until every box is evidenced. External
credentials (Supabase project, Lemon Squeezy account, CodeRabbit app) are
the only acceptable open items — each must name its exact blocker.
