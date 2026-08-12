from __future__ import annotations

import argparse
import json
from pathlib import Path

from .benchmark_baseline import (
    BenchmarkBaselineError,
    BenchmarkComparisonStatus,
    baseline_from_dict,
    compare_benchmark_to_baseline,
    create_benchmark_baseline,
)
from .benchmark_evidence import BenchmarkEvidenceError, load_benchmark_document
from .io_utils import atomic_write_text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="defeat-watermarker-benchmark-baseline",
        description=(
            "Create or compare runtime-aware content-addressed benchmark regression baselines."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="create a baseline from a verified benchmark report")
    create.add_argument("report", type=Path)
    create.add_argument("--output", type=Path, required=True)

    compare = sub.add_parser("compare", help="compare a verified report against a baseline")
    compare.add_argument("report", type=Path)
    compare.add_argument("--baseline", type=Path, required=True)
    compare.add_argument("--output", type=Path)
    return parser


def _load_baseline(path: Path):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BenchmarkBaselineError(f"could not read benchmark baseline: {exc}") from exc
    if not isinstance(payload, dict):
        raise BenchmarkBaselineError("benchmark baseline must be a JSON object")
    return baseline_from_dict(payload)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        report = load_benchmark_document(args.report)
        if args.command == "create":
            baseline = create_benchmark_baseline(report)
            atomic_write_text(
                args.output,
                json.dumps(baseline.to_dict(), indent=2, sort_keys=True) + "\n",
            )
            print(f"Baseline ID: {baseline.baseline_id}")
            print(f"Baseline: {args.output}")
            return 0

        baseline = _load_baseline(args.baseline)
        comparison = compare_benchmark_to_baseline(report, baseline)
        rendered = json.dumps(comparison.to_dict(), indent=2, sort_keys=True) + "\n"
        if args.output is None:
            print(rendered, end="")
        else:
            atomic_write_text(args.output, rendered)
        if comparison.status is BenchmarkComparisonStatus.REGRESSION:
            return 2
        if comparison.status is BenchmarkComparisonStatus.INDETERMINATE:
            return 3
        return 0
    except (
        OSError,
        UnicodeError,
        BenchmarkBaselineError,
        BenchmarkEvidenceError,
        ValueError,
    ) as exc:
        parser.error(str(exc))
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
