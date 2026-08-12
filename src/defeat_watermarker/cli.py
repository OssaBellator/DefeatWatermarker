from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .adapters.c2pa import C2paPythonBackend, C2paTrustPolicy, C2paVerifierAdapter
from .adapters.metadata import ContainerHintAdapter
from .capabilities import capability_document
from .detector_plugins import load_detector_plugins
from .engine import RobustnessEngine
from .evidence import (
    EvidenceError,
    build_evidence_bundle,
    load_evidence_document,
    verify_evidence_document,
)
from .interoperability import InteroperabilityError, run_interoperability_matrix
from .io_utils import atomic_write_text, read_bounded_bytes
from .metrics import GatePolicy, GateStatus, apply_gate, summarize_report
from .models import Artifact, Modality
from .mutations import (
    ByteCopyMutation,
    CenterCrop90Quality85,
    FfmpegH264Crf23,
    FfmpegScale75H264Crf23,
    IdentityMutation,
    JpegReencodeQuality85,
    NormalizeLineEndingsLf,
    NormalizeUnicodeNfc,
    Resize75Quality85,
    StripTrailingHorizontalWhitespace,
    WavPcm16DownmixMono,
    WavPcm16GainMinus3Db,
    WavPcm16Resample16Khz,
)
from .profiles import ProfileError, ReadinessStatus, assess_profile, load_profile
from .registry import AdapterRegistry
from .reliability import ReliabilityError, run_reliability_benchmark
from .scan_evidence import build_scan_evidence
from .suites import SuiteError, load_suite

_MAX_TRUST_ANCHOR_BYTES = 1024 * 1024


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
        atomic_write_text(output, rendered)


def _load_trust_anchors(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        data = read_bounded_bytes(path, max_bytes=_MAX_TRUST_ANCHOR_BYTES).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("C2PA trust-anchor file must be UTF-8 PEM text") from exc
    if "-----BEGIN CERTIFICATE-----" not in data:
        raise ValueError("C2PA trust-anchor file does not contain a PEM certificate")
    return data


def _registry(
    trust_anchors_path: Path | None = None,
    detector_plugins: tuple[str, ...] = (),
) -> AdapterRegistry:
    adapters = [ContainerHintAdapter()]
    anchors = _load_trust_anchors(trust_anchors_path)
    if C2paPythonBackend.available():
        adapters.append(
            C2paVerifierAdapter(
                policy=C2paTrustPolicy(
                    trust_anchors_pem=anchors,
                    remote_manifest_fetch=False,
                )
            )
        )
    elif anchors is not None:
        raise ValueError(
            "C2PA trust anchors were supplied but c2pa-python is not installed; "
            "install defeat-watermarker[c2pa]"
        )
    registry = AdapterRegistry(adapters)
    for adapter in load_detector_plugins(detector_plugins):
        registry.register(adapter)
    return registry


def _mutations():
    return [
        IdentityMutation(),
        ByteCopyMutation(),
        JpegReencodeQuality85(),
        Resize75Quality85(),
        CenterCrop90Quality85(),
        WavPcm16GainMinus3Db(),
        WavPcm16DownmixMono(),
        WavPcm16Resample16Khz(),
        NormalizeUnicodeNfc(),
        NormalizeLineEndingsLf(),
        StripTrailingHorizontalWhitespace(),
        FfmpegH264Crf23(),
        FfmpegScale75H264Crf23(),
    ]


def _scan(
    path: Path,
    media_type: str,
    output: Path | None,
    trust: Path | None,
    detector_plugins: tuple[str, ...] = (),
) -> int:
    artifact = Artifact(
        data=read_bounded_bytes(path),
        media_type=media_type,
        name=path.name,
        modality=_infer_modality(media_type),
    )
    scan = build_scan_evidence(artifact, _registry(trust, detector_plugins))
    _emit(scan.to_dict(), output)
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


def _validate_profile(path: Path) -> int:
    profile = load_profile(path)
    _emit(
        {
            "valid": True,
            "profile_id": profile.profile_id,
            "version": profile.version,
            "applies_from": profile.applies_from,
            "digest": profile.digest,
        },
        None,
    )
    return 0


def _assess_profile(path: Path, suite_paths: list[Path]) -> int:
    profile = load_profile(path)
    suites = tuple(load_suite(suite_path) for suite_path in suite_paths)
    assessment = assess_profile(profile, suites)
    _emit(assessment.to_dict(), None)
    return 0 if assessment.status is ReadinessStatus.READY else 5


def _run_reliability(corpus_path: Path, output: Path | None, trust: Path | None) -> int:
    report = run_reliability_benchmark(corpus_path, _registry(trust))
    _emit(report.to_dict(), output)
    return 0


def _run_interoperability(matrix_path: Path, output: Path | None, trust: Path | None) -> int:
    report = run_interoperability_matrix(matrix_path, _registry(trust))
    _emit(report.to_dict(), output)
    return 0


def _evaluate(
    path: Path,
    suite_path: Path,
    media_type: str,
    output: Path | None,
    trust: Path | None,
    min_survival_rate: float | None,
    min_verification_survival_rate: float | None,
    min_trust_survival_rate: float | None,
    min_provenance_id_preservation_rate: float | None,
    detector_plugins: tuple[str, ...] = (),
) -> int:
    suite = load_suite(suite_path)
    artifact = Artifact(
        data=read_bounded_bytes(path),
        media_type=media_type,
        name=path.name,
        modality=_infer_modality(media_type),
    )
    engine = RobustnessEngine(_registry(trust, detector_plugins), _mutations())
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
        artifact, suite, report, summary, gate_policy=gate_policy, gate=gate
    )
    _emit(evidence.to_dict(), output)
    return exit_code


def _add_detector_plugin_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--detector-plugin",
        action="append",
        default=[],
        metavar="NAME",
        help="explicitly load one installed read-only detector plugin; repeatable",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="defeat-watermarker",
        description="Anti-watermark and provenance robustness harness",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("capabilities", help="show adapters/mutations and dependency state")

    scan = subparsers.add_parser("scan", help="inspect an artifact for provenance signals")
    scan.add_argument("path", type=Path)
    scan.add_argument("--media-type", default="application/octet-stream")
    scan.add_argument("--output", type=Path)
    scan.add_argument("--c2pa-trust-anchors", type=Path)
    _add_detector_plugin_argument(scan)

    suite = subparsers.add_parser("suite", help="work with immutable robustness suites")
    suite_sub = suite.add_subparsers(dest="suite_command", required=True)
    validate = suite_sub.add_parser("validate", help="validate and digest a suite")
    validate.add_argument("path", type=Path)

    evidence = subparsers.add_parser("evidence", help="verify content-addressed evidence")
    evidence_sub = evidence.add_subparsers(dest="evidence_command", required=True)
    verify = evidence_sub.add_parser("verify", help="verify evidence digests offline")
    verify.add_argument("path", type=Path)
    verify.add_argument("--suite", type=Path)

    profile = subparsers.add_parser("profile", help="assess engineering-readiness profiles")
    profile_sub = profile.add_subparsers(dest="profile_command", required=True)
    profile_validate = profile_sub.add_parser("validate", help="validate and digest a profile")
    profile_validate.add_argument("path", type=Path)
    profile_assess = profile_sub.add_parser("assess", help="assess capabilities/suite coverage")
    profile_assess.add_argument("path", type=Path)
    profile_assess.add_argument("--suite", type=Path, action="append", default=[])

    benchmark = subparsers.add_parser("benchmark", help="run fixed detector benchmarks")
    benchmark_sub = benchmark.add_subparsers(dest="benchmark_command", required=True)
    reliability = benchmark_sub.add_parser("reliability", help="run a labelled reliability corpus")
    reliability.add_argument("corpus", type=Path)
    reliability.add_argument("--output", type=Path)
    reliability.add_argument("--c2pa-trust-anchors", type=Path)
    interoperability = benchmark_sub.add_parser(
        "interoperability", help="run a fixed multi-adapter agreement matrix"
    )
    interoperability.add_argument("matrix", type=Path)
    interoperability.add_argument("--output", type=Path)
    interoperability.add_argument("--c2pa-trust-anchors", type=Path)

    evaluate = subparsers.add_parser("evaluate", help="run a predefined robustness suite")
    evaluate.add_argument("path", type=Path)
    evaluate.add_argument("--suite", type=Path, required=True)
    evaluate.add_argument("--media-type", default="application/octet-stream")
    evaluate.add_argument("--output", type=Path)
    evaluate.add_argument("--c2pa-trust-anchors", type=Path)
    _add_detector_plugin_argument(evaluate)
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
                tuple(args.detector_plugin),
            )
        if args.command == "suite" and args.suite_command == "validate":
            return _validate_suite(args.path)
        if args.command == "evidence" and args.evidence_command == "verify":
            return _verify_evidence(args.path, args.suite)
        if args.command == "profile" and args.profile_command == "validate":
            return _validate_profile(args.path)
        if args.command == "profile" and args.profile_command == "assess":
            return _assess_profile(args.path, args.suite)
        if args.command == "benchmark" and args.benchmark_command == "reliability":
            return _run_reliability(args.corpus, args.output, args.c2pa_trust_anchors)
        if args.command == "benchmark" and args.benchmark_command == "interoperability":
            return _run_interoperability(args.matrix, args.output, args.c2pa_trust_anchors)
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
                tuple(args.detector_plugin),
            )
    except (
        OSError,
        UnicodeError,
        EvidenceError,
        InteroperabilityError,
        ProfileError,
        ReliabilityError,
        SuiteError,
        ValueError,
        KeyError,
    ) as exc:
        parser.error(str(exc))
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
