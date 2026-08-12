from __future__ import annotations

import argparse
import json
from pathlib import Path

from .benchmark_evidence import (
    BenchmarkEvidenceError,
    load_benchmark_document,
    verify_benchmark_document,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="defeat-watermarker-benchmark-verify",
        description="Verify a content-addressed reliability or interoperability report.",
    )
    parser.add_argument("path", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = load_benchmark_document(args.path)
        result = verify_benchmark_document(payload)
    except (OSError, UnicodeError, BenchmarkEvidenceError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0 if result.valid else 4


if __name__ == "__main__":
    raise SystemExit(main())
