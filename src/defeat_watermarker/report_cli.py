from __future__ import annotations

import argparse
from pathlib import Path

from .io_utils import atomic_write_text
from .report import ReportError, render_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="defeat-watermarker-report",
        description=(
            "Render verified scan, attack, benchmark or detector-conformance evidence, "
            "or a verified batch directory, as a self-contained local HTML report."
        ),
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        rendered = render_report(args.input)
        atomic_write_text(args.output, rendered)
    except (OSError, UnicodeError, ReportError, ValueError) as exc:
        parser.error(str(exc))
    print(f"HTML report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
