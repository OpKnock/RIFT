# Release checklist — RIFT v1.0.0

- [ ] `pip install -e ".[dev]" -c constraints.txt` clean on Python 3.11
- [ ] `pytest` green (currently 220 tests)
- [ ] `python scripts/validate_migrations.py` ok (001→007 in order, RLS on)
- [ ] `python scripts/secret_scan.py` ok
- [ ] `python scripts/check_versions.py` ok (pyproject ↔ package ↔ health)
- [ ] `python -m rift.cli demo` prints futures + Guardian-ready candidates
- [ ] `python -m rift.cli serve` boots; `GET /api/health` → `status: ok`
- [ ] `GET /api/meta` lists capabilities/limits matching `docs/api.md`
- [ ] Migrations applied to staging Supabase in order; RLS verified per user
- [ ] Persistence smoke (staging): create → get → run → list with `user_id` scoping
- [ ] Billing smoke (only if credentials exist): checkout 201 + webhook 200 + duplicate replay flag + entitlement mapping
- [ ] Frontend smoke: twin sync, FORESIGHT trajectories, Guardian verdict, evidence panel render; 503/401/422 states shown honestly
- [ ] `CHANGELOG.md` entry matches this commit; version stays `1.0.0`
- [ ] GitHub Actions `test` + `validate` + `security` jobs green on the release commit

Do not declare PRODUCTION READY until every box is evidenced. Open gates
include infrastructure credentials (Supabase project, Lemon Squeezy
account, CodeRabbit app) AND substantive scientific/clinical gates: a
relevant real clinical dataset, a predefined clinical endpoint with
adequate independent event volume, real external validation, prospective
validation, and clinical review. Each open item must name its exact
blocker.
