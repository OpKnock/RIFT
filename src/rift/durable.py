"""Durable append-only JSONL store for clinical ledgers (Phases 15, 20 RPO).

In-memory ledgers lose everything on restart, which is why the prospective
and review ledgers could never meet an RPO target. JsonlStore gives them a
crash-safe backing: every append is flushed and fsynced before the call
returns, and the ledger replays the file on startup. One JSON object per
line, UTF-8, no external dependencies.

Fail-closed: a corrupt line aborts the load with the line number rather
than silently skipping data. Concurrent writers from multiple processes
are NOT supported — run one API process per ledger file (documented, not hidden).
"""
from __future__ import annotations

import json
import os


class JsonlStore:
    """Append-only JSONL file with fsync-on-append and strict replay."""

    def __init__(self, path: str) -> None:
        if not path or not str(path).strip():
            raise ValueError("JsonlStore requires a non-empty file path")
        self.path = str(path)
        parent = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(parent, exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, "a", encoding="utf-8"):
                pass

    def append(self, record: dict) -> None:
        """Append one JSON object; fsync before returning."""
        if not isinstance(record, dict):
            raise ValueError("JsonlStore only stores dict records")
        line = json.dumps(record, sort_keys=True, separators=(",", ":"))
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def load(self) -> list[dict]:
        """Replay every line. Corrupt lines raise with their line number."""
        records: list[dict] = []
        with open(self.path, "r", encoding="utf-8") as handle:
            for lineno, line in enumerate(handle, start=1):
                text = line.strip()
                if not text:
                    continue
                try:
                    record = json.loads(text)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"corrupt ledger line {lineno} in {self.path}: {exc}") from exc
                if not isinstance(record, dict):
                    raise ValueError(
                        f"corrupt ledger line {lineno} in {self.path}: not a JSON object")
                records.append(record)
        return records

    def count(self) -> int:
        return len(self.load())
