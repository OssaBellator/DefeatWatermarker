#!/usr/bin/env python3
from __future__ import annotations

import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQUIRED_SCRIPTS = {
    "defeat-watermarker",
    "defeat-watermarker-attack",
    "defeat-watermarker-ui",
    "defeat-watermarker-scan-verify",
    "defeat-watermarker-batch",
    "defeat-watermarker-batch-verify",
    "defeat-watermarker-benchmark-verify",
    "defeat-watermarker-benchmark-baseline",
    "defeat-watermarker-report",
}


def main() -> int:
    if sys.version_info < (3, 11):
        raise SystemExit("Python 3.11+ is required")
    pyproject = tomllib.loads(
        (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    project = pyproject.get("project")
    if not isinstance(project, dict) or project.get("name") != "defeat-watermarker":
        raise SystemExit("pyproject project metadata is invalid")
    scripts = project.get("scripts")
    if not isinstance(scripts, dict):
        raise SystemExit("pyproject [project.scripts] is missing")
    missing = sorted(REQUIRED_SCRIPTS - set(scripts))
    if missing:
        raise SystemExit("missing public CLI entry points: " + ", ".join(missing))
    invalid = sorted(
        name
        for name in REQUIRED_SCRIPTS
        if not isinstance(scripts[name], str) or ":" not in scripts[name]
    )
    if invalid:
        raise SystemExit("invalid public CLI entry points: " + ", ".join(invalid))
    print(
        f"OK: Python {sys.version_info.major}.{sys.version_info.minor} and "
        f"{len(REQUIRED_SCRIPTS)} public CLI entry points"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
