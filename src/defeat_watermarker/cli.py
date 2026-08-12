from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .adapters.c2pa import C2paPythonBackend, C2paVerifierAdapter
from .adapters.metadata import ContainerHintAdapter
from .engine import RobustnessEngine
from .evidence import build_evidence_bundle
from .metrics import GatePolicy, apply_gate, summarize_report
from .models import Artifact, Modality
from .mutations import (
    ByteCopyMutation,
    CenterCrop90Quality85,
    IdentityMutation,
    JpegReencodeQuality85,
    Resize75Quality85,
)
from .registry import AdapterRegistry
from .suites import SuiteError, load_suite


def _infer_modality(media_type: str) -> Modality:
    prefix = media_type.split("/", 1)[0].lower()
    return {
        "image": Modality.IMAGE,
        "video": Modality.VIDEO,
        "audio": Modality.AUDIO,
        "text": Modality.TEXT,
    }.get(prefix, Modality.UNKNOWN)


def _emit(payload: dict[str, Any], output: Path | None) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if output is None:
        print(rendered, end="")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")


def _registry() -> AdapterRegistry:
    adapters = [ContainerHintAdapter()]
    if C2paPythonBackend.available():
        adapters.append(C2paVerifierAdapter())
    return AdapterRegistry(adapters)


def _mutations():
    # Image mutation classes import Pillow only when applied. This keeps the core dependency-free.
    return [
        IdentityMutation(),
        ByteCopyMutation(),
        JpegReencodeQuality85(),
        Resize75Quality85(),
        CenterCrop90Quality85(),
    ]


def _scan(path: Path, media_type: str, output: Path | None) -> int:
    artifact = Artifact(
        data=path.read_bytes(),
        media_type=media_type,
        name=path.name,
        modality=_infer_modality(media_type),
    )
    results = [adapter.detect(artifact).to_dict() for adapter in _registry() if adapter.supports(artifact)]
    _emit({"artifact_name": artifact.name, "results": results}, output)
    return 0


def _validate_suite(path: Path) -> int:
    suite = load_suite(path)
    _emit(
        {
            "valid": True,
            "suite_id": suite.suite_id,
            "version": suite.version,
            "scenario_count": len(suite.scenarios),
            "digest": suite.digest,
        },
        None,
    )
    return 0


def _evaluate(
    path: Path,
    suite_path: Path,
    media_type: str,
    output: Path | None,
    min_survival_rate: float | None,
) -> int:
    suite = load_suite(suite_path)
    artifact = Artifact(
        data=path.read_bytes(),
        media_type=media_type,
        name=path.name,
        modality=_infer_modality(media_type),
    )
    engine = RobustnessEngine(_registry(), _mutations())
    report = engine.evaluate(artifact, suite.scenarios)
    summary = summarize_report(report)
    evidence = build_evidence_bundle(artifact, suite, report, summary)
    payload = evidence.to_dict()

    exit_code = 0
    if min_survival_rate is not None:
        gate = apply_gate(summary, GatePolicy(min_survival_rate=min_survival_rate))
        payload["gate"] = gate.to_dict()
        if gate.status.value == "fail":
            exit_code = 2
        elif gate.status.value == "indeterminate":
            exit_code = 3

    _emit(payload, output)
    return exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="defeat-watermarker",
        description="Defensive AI watermark/provenance robustness lab",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="inspect an artifact for known provenance hints")
    scan.add_argument("path", type=Path)
    scan.add_argument("--media-type", default="application/octet-stream")
    scan.add_argument("--output", type=Path)

    suite = subparsers.add_parser("suite", help="work with immutable robustness suites")
    suite_subparsers = suite.add_subparsers(dest="suite_command", required=True)
    validate = suite_subparsers.add_parser("validate", help="validate and digest a suite")
    validate.add_argument("path", type=Path)

    evaluate = subparsers.add_parser(
        "evaluate",
        help="run a predefined suite and emit content-addressed evidence",
    )
    evaluate.add_argument("path", type=Path)
    evaluate.add_argument("--suite", type=Path, required=True)
    evaluate.add_argument("--media-type", default="application/octet-stream")
    evaluate.add_argument("--output", type=Path)
    evaluate.add_argument("--min-survival-rate", type=float)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "scan":
            return _scan(args.path, args.media_type, args.output)
        if args.command == "suite" and args.suite_command == "validate":
            return _validate_suite(args.path)
        if args.command == "evaluate":
            return _evaluate(
                args.path,
                args.suite,
                args.media_type,
                args.output,
                args.min_survival_rate,
            )
    except (OSError, SuiteError, ValueError, KeyError) as exc:
        parser.error(str(exc))
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
