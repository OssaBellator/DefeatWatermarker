from __future__ import annotations

import argparse
import json
from pathlib import Path

from .scan_evidence import ScanEvidenceError, load_scan_document, verify_scan_document


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="defeat-watermarker-scan-verify",
        description="Verify the integrity of a content-addressed detector scan document.",
    )
    parser.add_argument("path", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = load_scan_document(args.path)
        result = verify_scan_document(payload)
    except (OSError, UnicodeError, ScanEvidenceError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0 if result.valid else 4


if __name__ == "__main__":
    raise SystemExit(main())
