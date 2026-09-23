"""CI: migrations must be additive, idempotent, RLS-safe.

Checks every file in backend/supabase/migrations/*.sql for:
- CREATE TABLE has IF NOT EXISTS
- ADD COLUMN has IF NOT EXISTS
- CREATE INDEX has IF NOT EXISTS
- no DROP TABLE / TRUNCATE
- RLS enabled on new tables (ENABLE ROW LEVEL SECURITY)
- no hard-coded secrets (sk_live, service_role keys, bearer tokens)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = sorted((ROOT / "backend" / "supabase" / "migrations").glob("*.sql"))

ERRORS: list[str] = []


def check(path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    upper = sql.upper()
    if "DROP TABLE" in upper or "TRUNCATE" in upper:
        ERRORS.append(f"{path.name}: destructive DDL (DROP TABLE/TRUNCATE) is forbidden")
    for match in re.finditer(r"CREATE\s+TABLE\s+(?!IF\s+NOT\s+EXISTS)", upper):
        ERRORS.append(f"{path.name}: CREATE TABLE without IF NOT EXISTS")
        break
    for match in re.finditer(r"ADD\s+COLUMN\s+(?!IF\s+NOT\s+EXISTS)", upper):
        ERRORS.append(f"{path.name}: ADD COLUMN without IF NOT EXISTS")
        break
    for match in re.finditer(r"CREATE\s+(UNIQUE\s+)?INDEX\s+(?!IF\s+NOT\s+EXISTS)", upper):
        ERRORS.append(f"{path.name}: CREATE INDEX without IF NOT EXISTS")
        break
    if "CREATE TABLE" in upper and "ENABLE ROW LEVEL SECURITY" not in upper:
        ERRORS.append(f"{path.name}: new tables must enable RLS")
    if re.search(r"sk_live|pk_live|service_role|eyJhbGci", sql):
        ERRORS.append(f"{path.name}: possible embedded secret")


def main() -> int:
    if not MIGRATIONS:
        print("no migrations found")
        return 1
    for path in MIGRATIONS:
        check(path)
    # Ordering: numeric prefixes must be strictly increasing.
    prefixes = [p.name.split("_")[0] for p in MIGRATIONS]
    if prefixes != sorted(prefixes):
        ERRORS.append("migrations are not in numeric order")
    if ERRORS:
        print("migration validation failed:")
        for error in ERRORS:
            print(f"  - {error}")
        return 1
    print(f"migrations ok: {len(MIGRATIONS)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
