from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from .batch import BatchError, run_batch
from .io_utils import atomic_write_text

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def _record_filename(index: int, relative_path: str) -> str:
    safe = _SAFE_NAME_RE.sub("_", relative_path).strip("._") or "artifact"
    return f"{index:03d}-{safe}.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="defeat-watermarker-batch",
        description=(
            "Run fixed anti-watermark suites or detector-only scans across a bounded set "
            "of artifacts and emit a content-addressed batch index."
        ),
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--scan-only", action="store_true")
    parser.add_argument("--c2pa-trust-anchors", type=Path)
    parser.add_argument(
        "--detector-plugin",
        action="append",
        default=[],
        metavar="NAME",
        help="explicitly load one installed read-only detector plugin; repeatable",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = run_batch(
            args.input,
            recursive=args.recursive,
            scan_only=args.scan_only,
            trust_anchors=args.c2pa_trust_anchors,
            detector_plugins=tuple(args.detector_plugin),
        )
        args.output_dir.mkdir(parents=True, exist_ok=True)
        records_dir = args.output_dir / "records"
        records_dir.mkdir(parents=True, exist_ok=True)

        index_payload = result.to_dict()
        written_records: list[dict[str, object]] = []
        for index, record in enumerate(result.records, start=1):
            record_index = record.to_index_dict()
            if record.record is not None:
                filename = _record_filename(index, record.relative_path)
                atomic_write_text(
                    records_dir / filename,
                    json.dumps(record.record, indent=2, sort_keys=True) + "\n",
                )
                record_index["record_file"] = f"records/{filename}"
            else:
                record_index["record_file"] = None
            written_records.append(record_index)
        index_payload["records"] = written_records
        atomic_write_text(
            args.output_dir / "batch.json",
            json.dumps(index_payload, indent=2, sort_keys=True) + "\n",
        )
    except (OSError, UnicodeError, BatchError, ValueError, KeyError) as exc:
        parser.error(str(exc))

    print(f"Batch ID: {result.batch_id}")
    print(f"Artifacts: {len(result.records)}")
    print(f"Failures: {result.failed_records}")
    print(f"Batch index: {args.output_dir / 'batch.json'}")
    return 0 if result.failed_records == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
