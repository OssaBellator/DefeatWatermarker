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
from .regression_verify import (
    RegressionVerificationError,
    load_regression_report,
    verify_regression_report,
)


def _emit(payload: dict[str, object], output: Path | None) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if output is None:
        print(rendered, end="")
    else:
        atomic_write_text(output, rendered)


def _paths_alias(left: Path, right: Path) -> bool:
    try:
        if left.exists() and right.exists() and left.samefile(right):
            return True
    except OSError:
        pass
    try:
        return left.resolve(strict=False) == right.resolve(strict=False)
    except OSError:
        return left.absolute() == right.absolute()


def _reject_output_alias(output: Path | None, *inputs: Path) -> None:
    if output is None:
        return
    for input_path in inputs:
        if _paths_alias(output, input_path):
            raise RegressionError(
                f"regression output must not overwrite input: {input_path.name}"
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="defeat-watermarker-regression",
        description="Create, compare and verify content-addressed robustness regression evidence",
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

    verify = subparsers.add_parser(
        "verify",
        help="recompute and verify a saved regression report against its baseline/evidence",
    )
    verify.add_argument("baseline", type=Path)
    verify.add_argument("evidence", type=Path)
    verify.add_argument("report", type=Path)
    verify.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "baseline":
            _reject_output_alias(args.output, args.evidence)
            evidence = load_evidence_document(args.evidence)
            baseline = create_regression_baseline(
                evidence,
                baseline_id=args.id,
                version=args.version,
                max_drop=args.max_drop,
            )
            # Emit the published baseline schema exactly. baseline.digest is derived from
            # this document and is bound into later comparison reports; storing it here
            # would make the CLI create a file that load_regression_baseline rejects.
            _emit(baseline.to_dict(), args.output)
            return 0
        if args.command == "check":
            _reject_output_alias(args.output, args.baseline, args.evidence)
            baseline = load_regression_baseline(args.baseline)
            evidence = load_evidence_document(args.evidence)
            report = compare_regression(baseline, evidence)
            _emit(report.to_dict(), args.output)
            if report.status is RegressionStatus.FAIL:
                return 6
            if report.status is RegressionStatus.INDETERMINATE:
                return 7
            return 0
        if args.command == "verify":
            _reject_output_alias(
                args.output,
                args.baseline,
                args.evidence,
                args.report,
            )
            baseline = load_regression_baseline(args.baseline)
            evidence = load_evidence_document(args.evidence)
            report = load_regression_report(args.report)
            verification = verify_regression_report(report, baseline, evidence)
            _emit(verification.to_dict(), args.output)
            return 0 if verification.valid else 8
    except (
        OSError,
        UnicodeError,
        EvidenceError,
        RegressionError,
        RegressionVerificationError,
        ValueError,
    ) as exc:
        parser.error(str(exc))
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
