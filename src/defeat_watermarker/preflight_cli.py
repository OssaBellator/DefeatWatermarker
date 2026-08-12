from __future__ import annotations

import argparse
import json
from pathlib import Path

from .preflight import PreflightStatus, preflight_suite
from .suites import SuiteError, load_suite


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m defeat_watermarker.preflight_cli",
        description="Check whether every mutation in a fixed suite is runnable before evaluation",
    )
    parser.add_argument("suite", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        report = preflight_suite(load_suite(args.suite))
    except (OSError, UnicodeError, SuiteError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return 0 if report.status is PreflightStatus.READY else 9


if __name__ == "__main__":
    raise SystemExit(main())
