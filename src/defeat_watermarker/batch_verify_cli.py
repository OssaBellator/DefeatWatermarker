from __future__ import annotations

import argparse
import json
from pathlib import Path

from .batch_verify import BatchVerificationError, verify_batch_directory


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="defeat-watermarker-batch-verify",
        description="Verify a content-addressed batch index and all referenced scan/attack records.",
    )
    parser.add_argument("directory", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = verify_batch_directory(args.directory)
    except (OSError, UnicodeError, BatchVerificationError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0 if result.valid else 4


if __name__ == "__main__":
    raise SystemExit(main())
