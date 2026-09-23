"""CI: fail when credential-shaped strings are committed.

Scans source, docs, workflows, and frontend for live-secret patterns.
Env examples must keep values empty. This is a tripwire, not a full
secret manager: false positives should be allow-listed explicitly.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = [
    r"sk_live_[A-Za-z0-9]+",
    r"pk_live_[A-Za-z0-9]+",
    r"whsec_[A-Za-z0-9_\-]+",
    r"eyJhbGciOiJIUzI1NiJ9\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+",  # JWT-shaped
    r"-----BEGIN (RSA )?PRIVATE KEY-----",
    r"AKIA[0-9A-Z]{16}",
]
SCAN_GLOBS = ["src/**/*.py", "web/**/*", "docs/**/*.md", "*.md", ".env.example", ".github/**/*"]


def main() -> int:
    hits: list[str] = []
    files: list[Path] = []
    for glob in SCAN_GLOBS:
        files.extend(ROOT.glob(glob))
    for path in files:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="strict")
        except (UnicodeDecodeError, OSError):
            continue
        for pattern in PATTERNS:
            if re.search(pattern, text):
                hits.append(f"{path.relative_to(ROOT)}: matches {pattern}")
    if hits:
        print("secret scan failed:")
        for hit in hits:
            print(f"  - {hit}")
        return 1
    print(f"secret scan ok: {len(files)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
