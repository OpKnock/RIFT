# Upgrade Guide

This document describes how to upgrade RIFT between versions and the compatibility guarantees.

## Versioning Policy

RIFT follows [Semantic Versioning](https://semver.org/):
- **MAJOR** — Breaking changes to APIs, schemas, or contracts
- **MINOR** — New features, backward-compatible
- **PATCH** — Bug fixes, backward-compatible

## Upgrade Paths

### From 0.x to 1.0.0

**Breaking changes:**
- API endpoint structure reorganized under `/api/*`
- Experiment spec schema v2 (added `template_id`, `template_version`)
- Guardian verdict format changed (added `stages`, `action`, `findings`)
- Digital twin evidence bundle schema v2
- Configuration moved to `.env` / environment variables
- Database schema migrations 001-007 required

**Migration steps:**
```bash
# 1. Backup data
./local.sh stop
cp -r data data.backup.$(date +%Y%m%d)

# 2. Update code
git pull origin main

# 3. Run migrations (automatic on next start)
./local.sh start

# 4. Verify
./local.sh health
./local.sh test
```

### From 1.x to 1.y (Minor)

**Always safe:**
- New API endpoints (additive)
- New Guardian rules (additive, opt-in)
- New experiment templates
- New benchmark datasets
- Performance improvements

**May require config updates:**
- New environment variables (documented in release notes)
- New Guardian rules (opt-in via config)
- New metrics in Prometheus (additive)

### From 1.x to 2.0.0 (Future)

Planned breaking changes:
- Plugin API v2 (new manifest format)
- WebSocket protocol v2
- Digital twin evidence bundle v3
- Experiment spec schema v3

## Compatibility Guarantees

| Component | Guarantee |
|-----------|-----------|
| REST API | Additive only within MAJOR |
| WebSocket Events | Additive only within MAJOR |
| Experiment Spec Schema | Additive within MINOR, breaking in MAJOR |
| Guardian Verdict Format | Additive within MINOR, breaking in MAJOR |
| Evidence Bundle Schema | Additive within MINOR, breaking in MAJOR |
| Database Migrations | Forward-only, no downgrade |
| Plugin API | Additive within MINOR, breaking in MAJOR |
| Configuration Schema | Additive within MINOR, breaking in MAJOR |

## Deprecation Policy

- Deprecated features marked in docs and code for at least 1 MINOR version
- Deprecation warnings in logs (configurable)
- Removal only in next MAJOR version
- Migration path documented for each deprecation

## Rollback Procedure

```bash
# 1. Stop services
./local.sh stop

# 2. Restore database from backup
rm rift_local.db
cp data.backup.YYYYMMDD/rift_local.db .

# 3. Checkout previous version
git checkout v1.x.y

# 4. Restart
./local.sh start

# 5. Verify
./local.sh health
```

## Version Support Matrix

| Version | Release Date | EOL Date | Supported |
|---------|-------------|----------|-----------|
| 1.0.x   | 2026-09-27  | 2027-09-27 | ✅ |
| 0.9.x   | 2026-09-20  | 2026-12-20 | ⚠️ Security only |
| 0.8.x   | 2026-09-15  | 2026-09-15 | ❌ |

## Reporting Issues

If you encounter upgrade issues:
1. Check this guide for known issues
2. Search existing GitHub issues
3. Create new issue with:
   - Current version
   - Target version
   - Error messages
   - Steps to reproduce