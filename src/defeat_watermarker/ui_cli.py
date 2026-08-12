from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from pathlib import Path

from .builtin_suites import builtin_suite_catalog, builtin_suite_for
from .cli import _infer_modality, _mutations, _registry
from .engine import RobustnessEngine
from .evidence import build_evidence_bundle
from .io_utils import atomic_write_text, read_bounded_bytes
from .metrics import RobustnessSummary, summarize_report
from .models import Artifact, DetectionResult, EvaluationReport, Modality
from .suites import RobustnessSuite, load_suite


def _guess_media_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def _prompt_path() -> Path:
    if not sys.stdin.isatty():
        raise ValueError("artifact path is required in non-interactive mode")
    value = input("Artifact path: ").strip()
    if not value:
        raise ValueError("artifact path is required")
    return Path(value)


def _status(value: bool | None) -> str:
    if value is None:
        return "n/a"
    return "yes" if value else "NO"


def _percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:5.1f}%"


def _clip(value: str | None, width: int = 36) -> str:
    if not value:
        return "-"
    return value if len(value) <= width else value[: width - 1] + "…"


def _table(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> str:
    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))
    line = "  ".join("-" * width for width in widths)
    rendered = [
        "  ".join(header.ljust(widths[index]) for index, header in enumerate(headers)),
        line,
    ]
    rendered.extend(
        "  ".join(cell.ljust(widths[index]) for index, cell in enumerate(row))
        for row in rows
    )
    return "\n".join(rendered)


def _baseline_table(results: tuple[DetectionResult, ...]) -> str:
    rows = [
        (
            item.adapter_id,
            item.family.value,
            _status(item.detected),
            f"{item.confidence:.3f}",
            item.verification_state.value,
            _clip(item.provenance_identifier),
        )
        for item in results
    ]
    if not rows:
        return "No compatible detector adapters are available for this artifact."
    return _table(
        ("adapter", "family", "detected", "confidence", "verification", "provenance id"),
        rows,
    )


def _scenario_table(report: EvaluationReport) -> str:
    rows: list[tuple[str, ...]] = []
    for scenario_result in report.scenarios:
        scenario = scenario_result.scenario
        if not scenario_result.comparisons:
            rows.append((scenario.scenario_id, "-", "n/a", "n/a", "n/a", "n/a", "n/a"))
            continue
        for comparison in scenario_result.comparisons:
            rows.append(
                (
                    scenario.scenario_id,
                    comparison.adapter_id,
                    _status(comparison.survived),
                    f"{comparison.confidence_delta:+.3f}",
                    _status(comparison.verification_survived),
                    _status(comparison.trust_survived),
                    _status(comparison.provenance_identifier_preserved),
                )
            )
    return _table(
        (
            "attack scenario",
            "adapter",
            "detected after",
            "confidence Δ",
            "crypto survives",
            "trust survives",
            "id preserved",
        ),
        rows,
    )


def _summary_lines(summary: RobustnessSummary) -> list[str]:
    return [
        f"Detection survival:      {_percent(summary.survival_rate)} "
        f"({summary.survived}/{summary.evaluated_comparisons})",
        f"Crypto survival:         {_percent(summary.verification_survival_rate)} "
        f"({summary.verification_survived}/{summary.verified_comparisons})",
        f"Trust survival:          {_percent(summary.trust_survival_rate)} "
        f"({summary.trust_survived}/{summary.trusted_comparisons})",
        f"Provenance ID preserved: {_percent(summary.provenance_id_preservation_rate)} "
        f"({summary.provenance_id_preserved}/{summary.provenance_id_comparisons})",
    ]


def _print_header(artifact: Artifact, suite: RobustnessSuite | None) -> None:
    print("\nDefeatWatermarker — anti-watermark console")
    print("=" * 46)
    print(f"Artifact:   {artifact.name}")
    print(f"Media type: {artifact.media_type}")
    print(f"Modality:   {artifact.modality.value}")
    if suite is None:
        print("Attack:     scan only")
    else:
        print(f"Attack:     {suite.suite_id} v{suite.version}")
        print(f"Suite hash: {suite.digest}")


def _write_evidence(path: Path, evidence: dict[str, object]) -> None:
    atomic_write_text(path, json.dumps(evidence, indent=2, sort_keys=True) + "\n")


def _run(
    artifact_path: Path,
    media_type: str,
    suite_path: Path | None,
    *,
    scan_only: bool,
    json_output: Path | None,
    trust_anchors: Path | None,
) -> int:
    artifact = Artifact(
        data=read_bounded_bytes(artifact_path),
        media_type=media_type,
        name=artifact_path.name,
        modality=_infer_modality(media_type),
    )
    registry = _registry(trust_anchors)
    suite: RobustnessSuite | None = None
    if not scan_only:
        suite = load_suite(suite_path) if suite_path is not None else builtin_suite_for(artifact.modality)

    _print_header(artifact, suite)

    baseline = tuple(
        adapter.detect(artifact)
        for adapter in registry
        if adapter.supports(artifact)
    )
    print("\nDetector/model output")
    print("---------------------")
    print(_baseline_table(baseline))

    if scan_only or suite is None:
        if not scan_only and suite is None:
            print(
                "\nNo built-in attack suite exists for this modality; showing detector output only. "
                "Pass --suite PATH to run a custom fixed suite."
            )
        return 0

    engine = RobustnessEngine(registry, _mutations())
    report = engine.evaluate(artifact, suite.scenarios)
    summary = summarize_report(report)
    evidence = build_evidence_bundle(artifact, suite, report, summary).to_dict()

    print("\nAnti-watermark attack results")
    print("-----------------------------")
    print(_scenario_table(report))
    print("\nSummary")
    print("-------")
    for line in _summary_lines(summary):
        print(line)
    print(f"Evidence ID: {evidence['evidence_id']}")

    if json_output is not None:
        _write_evidence(json_output, evidence)
        print(f"Full JSON evidence: {json_output}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="defeat-watermarker-ui",
        description=(
            "Guided console UI: input an artifact and inspect detector output plus fixed "
            "anti-watermark attack results."
        ),
    )
    parser.add_argument("artifact", type=Path, nargs="?")
    parser.add_argument("--media-type", help="MIME type; inferred from filename when omitted")
    parser.add_argument("--suite", type=Path, help="custom immutable attack-suite JSON")
    parser.add_argument("--scan-only", action="store_true", help="show detector output without attacks")
    parser.add_argument("--json-output", type=Path, help="write the full evidence bundle as JSON")
    parser.add_argument("--c2pa-trust-anchors", type=Path)
    parser.add_argument("--list-builtins", action="store_true", help="list built-in attack suites")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.list_builtins:
            for suite in builtin_suite_catalog():
                modalities = sorted({scenario.modality.value for scenario in suite.scenarios})
                print(f"{suite.suite_id:<32} {','.join(modalities):<8} {len(suite.scenarios)} scenarios")
            return 0
        artifact = args.artifact if args.artifact is not None else _prompt_path()
        media_type = args.media_type or _guess_media_type(artifact)
        return _run(
            artifact,
            media_type,
            args.suite,
            scan_only=args.scan_only,
            json_output=args.json_output,
            trust_anchors=args.c2pa_trust_anchors,
        )
    except (OSError, UnicodeError, ValueError, KeyError) as exc:
        parser.error(str(exc))
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
