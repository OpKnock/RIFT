"""CI: pyproject, package, and health endpoint must agree on the version."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    if not match:
        print("version not found in pyproject.toml")
        return 1
    expected = match.group(1)
    init = (ROOT / "src" / "rift" / "__init__.py").read_text(encoding="utf-8")
    if f'__version__ = "{expected}"' not in init:
        print(f"src/rift/__init__.py does not match {expected}")
        return 1
    api = (ROOT / "src" / "rift" / "api.py").read_text(encoding="utf-8")
    if "ENGINE_VERSION" not in api and expected not in api:
        print(f"src/rift/api.py health payload missing version {expected}")
        return 1
    print(f"versions ok: {expected}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
