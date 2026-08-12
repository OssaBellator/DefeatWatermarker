from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .attack_plan import AttackPlanError, build_attack_plan
from .cli import main as core_main
from .suites import SuiteError, load_suite


def _plan(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="defeat-watermarker-attack plan",
        description="Freeze a reviewed anti-watermark attack plan before any detector runs",
    )
    parser.add_argument("suite", type=Path)
    parser.add_argument(
        "--max-severity",
        choices=("control", "low", "medium", "high"),
        default="high",
    )
    args = parser.parse_args(argv)
    try:
        plan = build_attack_plan(load_suite(args.suite), max_severity=args.max_severity)
    except (OSError, SuiteError, AttackPlanError) as exc:
        parser.error(str(exc))
    print(json.dumps(plan.to_dict(), indent=2, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run or pre-commit a fixed anti-watermark stress workflow.

    Normal arguments are forwarded to ``defeat-watermarker evaluate``. The
    ``plan`` subcommand reads only the immutable suite document and emits the
    exact content-addressed attack plan; it never opens an artifact or invokes
    a detector.
    """

    forwarded = list(sys.argv[1:] if argv is None else argv)
    if forwarded and forwarded[0] == "plan":
        return _plan(forwarded[1:])
    return core_main(["evaluate", *forwarded])


if __name__ == "__main__":
    raise SystemExit(main())
