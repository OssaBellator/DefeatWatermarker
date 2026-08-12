from __future__ import annotations

import argparse
import json
from pathlib import Path

from .evidence import EvidenceError, load_evidence_document
from .io_utils import atomic_write_text
from .regression import (
    RegressionError,
    RegressionStatus,
    compare_regression,
    create_regression_baseline,
    load_regression_baseline,
)


def _emit(payload: dict[str, object], output: Path | None) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if output is None:
        print(rendered, end="")
    else:
        atomic_write_text(output, rendered)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="defeat-watermarker-regression",
        description="Create and compare content-addressed robustness regression baselines",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    baseline = subparsers.add_parser("baseline", help="create a baseline from verified evidence")
    baseline.add_argument("evidence", type=Path)
    baseline.add_argument("--id", required=True)
    baseline.add_argument("--version", required=True)
    baseline.add_argument("--max-drop", type=float, default=0.0)
    baseline.add_argument("--output", type=Path)

    check = subparsers.add_parser("check", help="compare verified evidence with a baseline")
    check.add_argument("baseline", type=Path)
    check.add_argument("evidence", type=Path)
    check.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "baseline":
            evidence = load_evidence_document(args.evidence)
            baseline = create_regression_baseline(
                evidence,
                baseline_id=args.id,
                version=args.version,
                max_drop=args.max_drop,
            )
            _emit({"baseline_digest": baseline.digest, **baseline.to_dict()}, args.output)
            return 0
        if args.command == "check":
            baseline = load_regression_baseline(args.baseline)
            evidence = load_evidence_document(args.evidence)
            report = compare_regression(baseline, evidence)
            _emit(report.to_dict(), args.output)
            if report.status is RegressionStatus.FAIL:
                return 6
            if report.status is RegressionStatus.INDETERMINATE:
                return 7
            return 0
    except (OSError, UnicodeError, EvidenceError, RegressionError, ValueError) as exc:
        parser.error(str(exc))
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
