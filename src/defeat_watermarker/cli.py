from __future__ import annotations

import argparse
import json
from pathlib import Path

from .adapters.metadata import ContainerHintAdapter
from .models import Artifact
from .registry import AdapterRegistry


def _scan(path: Path, media_type: str) -> int:
    artifact = Artifact(data=path.read_bytes(), media_type=media_type, name=path.name)
    registry = AdapterRegistry([ContainerHintAdapter()])
    results = [adapter.detect(artifact).to_dict() for adapter in registry]
    print(json.dumps({"artifact_name": artifact.name, "results": results}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="defeat-watermarker",
        description="Defensive AI watermark/provenance robustness lab",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    scan = subparsers.add_parser("scan", help="inspect an artifact for known provenance hints")
    scan.add_argument("path", type=Path)
    scan.add_argument("--media-type", default="application/octet-stream")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "scan":
        return _scan(args.path, args.media_type)
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
