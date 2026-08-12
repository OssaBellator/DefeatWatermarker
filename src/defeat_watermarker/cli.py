from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .adapters.c2pa import C2paPythonBackend, C2paTrustPolicy, C2paVerifierAdapter
from .adapters.metadata import ContainerHintAdapter
from .capabilities import capability_document
from .engine import RobustnessEngine
from .evidence import (
    EvidenceError,
    build_evidence_bundle,
    load_evidence_document,
    verify_evidence_document,
)
from .metrics import GatePolicy, GateStatus, apply_gate, summarize_report
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
        "application": Modality.DOCUMENT if media_type == "application/pdf" else Modality.UNKNOWN,
    }.get(prefix, Modality.UNKNOWN)


def _emit(payload: dict[str, Any], output: Path | None) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if output is None:
        print(rendered, end="")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")


def _load_trust_anchors(path: Path | None) -> str | None:
    if path is None:
        return None
    data = path.read_text(encoding="utf-8")
    if "-----BEGIN CERTIFICATE-----" not in data:
        raise ValueError("C2PA trust-anchor file does not contain a PEM certificate")
    return data


def _registry(trust_anchors_path: Path | None = None) -> AdapterRegistry:
    adapters = [ContainerHintAdapter()]
    anchors = _load_trust_anchors(trust_anchors_path)
    if C2paPythonBackend.available():
        adapters.append(
            C2paVerifierAdapter(
                policy=C2paTrustPolicy(
                    trust_anchors_pem=anchors,
                    verify_cert_anchors=anchors is not None,
                    remote_manifest_fetch=False,
                )
            )
        )
    elif anchors is not None:
        raise ValueError(
            "C2PA trust anchors were supplied but c2pa-python is not installed; "
            "install defeat-watermarker[c2pa]"
        )
    return AdapterRegistry(adapters)


def _mutations():
    return [
        IdentityMutation(),
        ByteCopyMutation(),
        JpegReencodeQuality85(),
        Resize75Quality85(),
        CenterCrop90Quality85(),
    ]


def _scan(
    path: Path,
    media_type: str,
    output: Path | None,
    c2pa_trust_anchors: Path | None,
) -> int:
    artifact = Artifact(
        data=path.read_bytes(),
        media_type=media_type,
        name=path.name,
        modality=_infer_modality(media_type),
    )
    results = [
        adapter.detect(artifact).to_dict()
        for adapter in _registry(c2pa_trust_anchors)
        if adapter.supports(artifact)
    ]
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


def _verify_evidence(path: Path, suite_path: Path | None) -> int:
    payload = load_evidence_document(path)
    suite = load_suite(suite_path) if suite_path is not None else None
    result = verify_evidence_document(payload, suite=suite)
    _emit(result.to_dict(), None)
    return 0 if result.valid else 4


def _evaluate(
    path: Path,
    suite_path: Path,
    media_type: str,
    output: Path | None,
    c2pa_trust_anchors: Path | None,
    min_survival_rate: float | None,
    min_verification_survival_rate: float | None,
    min_trust_survival_rate: float | None,
    min_provenance_id_preservation_rate: float | None,
) -> int:
    suite = load_suite(suite_path)
    artifact = Artifact(
        data=path.read_bytes(),
        media_type=media_type,
        name=path.name,
        modality=_infer_modality(media_type),
    )
    engine = RobustnessEngine(_registry(c2pa_trust_anchors), _mutations())
    report = engine.evaluate(artifact, suite.scenarios)
    summary = summarize_report(report)

    thresholds = (
        min_survival_rate,
        min_verification_survival_rate,
        min_trust_survival_rate,
        min_provenance_id_preservation_rate,
    )
    gate_policy = None
    gate = None
    exit_code = 0
    if any(value is not None for value in thresholds):
        gate_policy = GatePolicy(
            min_survival_rate=min_survival_rate,
            min_verification_survival_rate=min_verification_survival_rate,
            min_trust_survival_rate=min_trust_survival_rate,
            min_provenance_id_preservation_rate=min_provenance_id_preservation_rate,
        )
        gate = apply_gate(summary, gate_policy)
        if gate.status is GateStatus.FAIL:
            exit_code = 2
        elif gate.status is GateStatus.INDETERMINATE:
            exit_code = 3

    evidence = build_evidence_bundle(
        artifact,
        suite,
        report,
        summary,
        gate_policy=gate_policy,
        gate=gate,
    )
    _emit(evidence.to_dict(), output)
    return exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="defeat-watermarker",
        description="Defensive AI watermark/provenance robustness lab",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "capabilities", help="show built-in adapters/mutations and optional dependency state"
    )

    scan = subparsers.add_parser("scan", help="inspect an artifact for known provenance hints")
    scan.add_argument("path", type=Path)
    scan.add_argument("--media-type", default="application/octet-stream")
    scan.add_argument("--output", type=Path)
    scan.add_argument("--c2pa-trust-anchors", type=Path)

    suite = subparsers.add_parser("suite", help="work with immutable robustness suites")
    suite_subparsers = suite.add_subparsers(dest="suite_command", required=True)
    validate = suite_subparsers.add_parser("validate", help="validate and digest a suite")
    validate.add_argument("path", type=Path)

    evidence = subparsers.add_parser("evidence", help="verify content-addressed evidence")
    evidence_subparsers = evidence.add_subparsers(dest="evidence_command", required=True)
    verify = evidence_subparsers.add_parser("verify", help="verify evidence digests offline")
    verify.add_argument("path", type=Path)
    verify.add_argument("--suite", type=Path)

    evaluate = subparsers.add_parser(
        "evaluate",
        help="run a predefined suite and emit content-addressed evidence",
    )
    evaluate.add_argument("path", type=Path)
    evaluate.add_argument("--suite", type=Path, required=True)
    evaluate.add_argument("--media-type", default="application/octet-stream")
    evaluate.add_argument("--output", type=Path)
    evaluate.add_argument("--c2pa-trust-anchors", type=Path)
    evaluate.add_argument("--min-survival-rate", type=float)
    evaluate.add_argument("--min-verification-survival-rate", type=float)
    evaluate.add_argument("--min-trust-survival-rate", type=float)
    evaluate.add_argument("--min-provenance-id-preservation-rate", type=float)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "capabilities":
            _emit(capability_document(), None)
            return 0
        if args.command == "scan":
            return _scan(
                args.path,
                args.media_type,
                args.output,
                args.c2pa_trust_anchors,
            )
        if args.command == "suite" and args.suite_command == "validate":
            return _validate_suite(args.path)
        if args.command == "evidence" and args.evidence_command == "verify":
            return _verify_evidence(args.path, args.suite)
        if args.command == "evaluate":
            return _evaluate(
                args.path,
                args.suite,
                args.media_type,
                args.output,
                args.c2pa_trust_anchors,
                args.min_survival_rate,
                args.min_verification_survival_rate,
                args.min_trust_survival_rate,
                args.min_provenance_id_preservation_rate,
            )
    except (OSError, UnicodeError, EvidenceError, SuiteError, ValueError, KeyError) as exc:
        parser.error(str(exc))
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
