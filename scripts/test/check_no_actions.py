#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[2]
workflow_dir = root / ".github" / "workflows"
files = (
    sorted(path for path in workflow_dir.glob("*.y*ml") if path.is_file())
    if workflow_dir.exists()
    else []
)
if files:
    print(
        "automatic GitHub workflow files are present while local-only testing is required:",
        file=sys.stderr,
    )
    for path in files:
        print(f" - {path.relative_to(root)}", file=sys.stderr)
    raise SystemExit(1)
print("OK: no GitHub Actions workflow files are enabled on this branch")
