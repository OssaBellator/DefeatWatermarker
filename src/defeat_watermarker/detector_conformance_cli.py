from __future__ import annotations

import argparse
import json
from pathlib import Path

from .detector_conformance import (
    load_conformance_document,
    run_detector_conformance,
    verify_conformance_document,
)
from .detector_plugins import DetectorPluginError, load_detector_plugins
from .io_utils import atomic_write_text, read_bounded_bytes
from .models import Artifact, Modality


def _infer_modality(media_type: str) -> Modality:
    prefix = media_type.split("/", 1)[0].lower()
    return {
        "image": Modality.IMAGE,
        "video": Modality.VIDEO,
        "audio": Modality.AUDIO,
        "text": Modality.TEXT,
        "application": (
            Modality.DOCUMENT if media_type == "application/pdf" else Modality.UNKNOWN
        ),
    }.get(prefix, Modality.UNKNOWN)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="defeat-watermarker-detector-conformance",
        description=(
            "Run or verify detector-only conformance checks for an explicitly enabled "
            "read-only detector plugin."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run conformance against one artifact")
    run.add_argument("path", type=Path)
    run.add_argument("--media-type", default="application/octet-stream")
    run.add_argument("--detector-plugin", required=True, metavar="NAME")
    run.add_argument("--output", type=Path)

    verify = sub.add_parser("verify", help="verify content-addressed conformance evidence")
    verify.add_argument("report", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "verify":
            result = verify_conformance_document(load_conformance_document(args.report))
            print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
            return 0 if result.valid else 4

        adapter = load_detector_plugins((args.detector_plugin,))[0]
        artifact = Artifact(
            data=read_bounded_bytes(args.path),
            media_type=args.media_type,
            name=args.path.name,
            modality=_infer_modality(args.media_type),
        )
        report = run_detector_conformance(args.detector_plugin, adapter, artifact)
        rendered = json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"
        if args.output is None:
            print(rendered, end="")
        else:
            atomic_write_text(args.output, rendered)
        return 0 if report.passed else 2
    except (
        OSError,
        UnicodeError,
        DetectorPluginError,
        ValueError,
        IndexError,
    ) as exc:
        parser.error(str(exc))
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
