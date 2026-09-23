"""Schema/code consistency: application payload keys must exist in migrations.

Catches the drift class where the API writes a column no migration created
(e.g. experiment_runs.user_id before migration 005). Parses migration SQL
for created/added columns and asserts every key the server persists is
covered. Unknown JSON blobs (scenario/result/metrics/...) are exempt.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION_DIR = ROOT / "backend" / "supabase" / "migrations"

# Columns inside free-form JSON payloads, not real table columns.
JSON_BLOB_KEYS = {"scenario", "result", "metrics", "raw", "payload"}

# What the server persists per table (must match api.py + supabase_store usage).
EXPERIMENTS_KEYS = {
    "name", "description", "scenario", "status", "user_id", "project_id",
    "perturbations", "policy_variables", "optimizer_config", "backend",
    "seed", "engine_version", "error", "fingerprint",
}
RUNS_KEYS = {
    "experiment_id", "optimizer", "result", "metrics", "seed", "backend",
    "optimizer_config", "engine_version", "error", "fingerprint", "user_id",
    "duration_ms", "constraint_violations",
}
BILLING_EVENT_KEYS = {
    "event_name", "supported", "provider_event_id", "idempotency_key",
    "lemon_customer_id", "lemon_subscription_id", "payload",
}
BILLING_SUBSCRIPTION_KEYS = {
    "user_id", "lemon_subscription_id", "lemon_customer_id", "status",
    "variant_id", "renews_at", "ends_at", "raw",
}


def _migration_columns() -> dict[str, set[str]]:
    columns: dict[str, set[str]] = {}
    for path in sorted(MIGRATION_DIR.glob("*.sql")):
        sql = path.read_text(encoding="utf-8")
        # ALTER TABLE statements may add several columns comma-separated;
        # attribute every ADD COLUMN in the statement to its table.
        for statement in re.split(r";", sql):
            table_match = re.search(
                r"alter\s+table\s+public\.(\w+)", statement, re.IGNORECASE
            )
            if table_match:
                table = table_match.group(1)
                for col in re.findall(
                    r"add\s+column\s+if\s+not\s+exists\s+(\w+)",
                    statement,
                    re.IGNORECASE,
                ):
                    columns.setdefault(table, set()).add(col)
        for match in re.finditer(
            r"create\s+table\s+if\s+not\s+exists\s+public\.(\w+)\s*\((.*?)\);",
            sql,
            re.IGNORECASE | re.DOTALL,
        ):
            table, body = match.group(1), match.group(2)
            for col in re.findall(r"^\s*(\w+)\s+", body, re.MULTILINE):
                if col.lower() not in ("constraint", "primary", "foreign", "unique", "check"):
                    columns.setdefault(table, set()).add(col)
    return columns


def test_experiment_columns_covered():
    columns = _migration_columns()
    known = columns.get("experiments", set()) | JSON_BLOB_KEYS
    missing = {key for key in EXPERIMENTS_KEYS if key not in known}
    assert not missing, f"experiments keys missing from migrations: {missing}"


def test_runs_columns_covered():
    columns = _migration_columns()
    known = columns.get("experiment_runs", set()) | JSON_BLOB_KEYS
    missing = {key for key in RUNS_KEYS if key not in known}
    assert not missing, f"experiment_runs keys missing from migrations: {missing}"


def test_billing_columns_covered():
    columns = _migration_columns()
    events = columns.get("billing_events", set()) | JSON_BLOB_KEYS
    subs = columns.get("billing_subscriptions", set()) | JSON_BLOB_KEYS
    assert not ({k for k in BILLING_EVENT_KEYS if k not in events}), "billing_events drift"
    assert not ({k for k in BILLING_SUBSCRIPTION_KEYS if k not in subs}), "billing_subscriptions drift"
