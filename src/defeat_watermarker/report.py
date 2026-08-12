from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from .batch_verify import BatchVerificationError, verify_batch_directory
from .benchmark_evidence import verify_benchmark_document
from .evidence import EvidenceError, load_evidence_document, verify_evidence_document
from .scan_evidence import ScanEvidenceError, load_scan_document, verify_scan_document


class ReportError(ValueError):
    """Raised when report input is unsupported or fails integrity verification."""


def _escape(value: Any) -> str:
    if value is None:
        return "—"
    return html.escape(str(value), quote=True)


def _bool(value: Any) -> str:
    if value is None:
        return "n/a"
    return "yes" if value is True else "no"


def _percent(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "n/a"
    return f"{float(value) * 100:.1f}%"


def _page(title: str, identifier: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="generator" content="DefeatWatermarker">
<title>{_escape(title)}</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 1200px; margin: 2rem auto; padding: 0 1rem; line-height: 1.45; }}
h1, h2 {{ line-height: 1.15; }}
code {{ overflow-wrap: anywhere; }}
table {{ border-collapse: collapse; width: 100%; margin: 1rem 0 2rem; }}
th, td {{ border-bottom: 1px solid #ccc; text-align: left; padding: .5rem; vertical-align: top; }}
th {{ background: #f5f5f5; }}
.meta {{ display: grid; grid-template-columns: max-content 1fr; gap: .35rem 1rem; }}
.good {{ font-weight: 600; }}
.small {{ font-size: .9rem; }}
</style>
</head>
<body>
<h1>{_escape(title)}</h1>
<p class="small"><strong>Content ID:</strong> <code>{_escape(identifier)}</code></p>
{body}
<hr>
<p class="small">Generated from verified content-addressed evidence. Source and derivative artifact bytes are not embedded in this report.</p>
</body>
</html>
"""


def _scan_html(payload: dict[str, Any]) -> str:
    verification = verify_scan_document(payload)
    if not verification.valid or verification.scan_id is None:
        raise ReportError("scan document failed integrity verification")
    artifact = payload["artifact"]
    rows = []
    for result in payload["results"]:
        rows.append(
            "<tr>"
            f"<td><code>{_escape(result.get('adapter_id'))}</code></td>"
            f"<td>{_escape(result.get('family'))}</td>"
            f"<td>{_bool(result.get('detected'))}</td>"
            f"<td>{_escape(result.get('confidence'))}</td>"
            f"<td>{_escape(result.get('verification_state'))}</td>"
            f"<td><code>{_escape(result.get('provenance_identifier'))}</code></td>"
            "</tr>"
        )
    body = f"""
<h2>Artifact</h2>
<div class="meta">
<div>Name</div><div>{_escape(artifact.get('name'))}</div>
<div>Media type</div><div>{_escape(artifact.get('media_type'))}</div>
<div>Modality</div><div>{_escape(artifact.get('modality'))}</div>
<div>SHA-256</div><div><code>{_escape(artifact.get('sha256'))}</code></div>
<div>Bytes</div><div>{_escape(artifact.get('byte_length'))}</div>
</div>
<h2>Detector/model output</h2>
<table><thead><tr><th>Adapter</th><th>Family</th><th>Detected</th><th>Confidence</th><th>Verification</th><th>Provenance ID</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
"""
    return _page("DefeatWatermarker scan report", verification.scan_id, body)


def _evaluation_html(payload: dict[str, Any]) -> str:
    verification = verify_evidence_document(payload)
    if not verification.valid or verification.evidence_id is None:
        raise ReportError("evaluation evidence failed integrity verification")
    artifact = payload["artifact"]
    report = payload["report"]
    baseline_rows = []
    for result in report.get("baseline", []):
        baseline_rows.append(
            "<tr>"
            f"<td><code>{_escape(result.get('adapter_id'))}</code></td>"
            f"<td>{_escape(result.get('family'))}</td>"
            f"<td>{_bool(result.get('detected'))}</td>"
            f"<td>{_escape(result.get('confidence'))}</td>"
            f"<td>{_escape(result.get('verification_state'))}</td>"
            "</tr>"
        )

    scenario_rows = []
    for scenario_result in report.get("scenarios", []):
        scenario = scenario_result.get("scenario", {})
        comparisons = scenario_result.get("comparisons", [])
        if not comparisons:
            scenario_rows.append(
                "<tr>"
                f"<td>{_escape(scenario.get('scenario_id'))}</td>"
                "<td>—</td><td>n/a</td><td>n/a</td><td>n/a</td><td>n/a</td><td>n/a</td>"
                "</tr>"
            )
            continue
        for comparison in comparisons:
            scenario_rows.append(
                "<tr>"
                f"<td>{_escape(scenario.get('scenario_id'))}</td>"
                f"<td><code>{_escape(comparison.get('adapter_id'))}</code></td>"
                f"<td>{_bool(comparison.get('survived'))}</td>"
                f"<td>{_escape(comparison.get('confidence_delta'))}</td>"
                f"<td>{_bool(comparison.get('verification_survived'))}</td>"
                f"<td>{_bool(comparison.get('trust_survived'))}</td>"
                f"<td>{_bool(comparison.get('provenance_identifier_preserved'))}</td>"
                "</tr>"
            )

    summary = payload.get("summary", {})
    body = f"""
<h2>Artifact</h2>
<div class="meta">
<div>Name</div><div>{_escape(artifact.get('name'))}</div>
<div>Media type</div><div>{_escape(artifact.get('media_type'))}</div>
<div>SHA-256</div><div><code>{_escape(artifact.get('sha256'))}</code></div>
<div>Suite</div><div>{_escape(payload.get('suite', {}).get('suite_id'))} {_escape(payload.get('suite', {}).get('version'))}</div>
</div>
<h2>Baseline detector/model output</h2>
<table><thead><tr><th>Adapter</th><th>Family</th><th>Detected</th><th>Confidence</th><th>Verification</th></tr></thead>
<tbody>{''.join(baseline_rows)}</tbody></table>
<h2>Fixed anti-watermark attack results</h2>
<table><thead><tr><th>Scenario</th><th>Adapter</th><th>Detected survives</th><th>Confidence Δ</th><th>Crypto survives</th><th>Trust survives</th><th>ID preserved</th></tr></thead>
<tbody>{''.join(scenario_rows)}</tbody></table>
<h2>Summary</h2>
<div class="meta">
<div>Detection survival</div><div>{_percent(summary.get('survival_rate'))}</div>
<div>Cryptographic survival</div><div>{_percent(summary.get('verification_survival_rate'))}</div>
<div>Trust survival</div><div>{_percent(summary.get('trust_survival_rate'))}</div>
<div>Provenance ID preservation</div><div>{_percent(summary.get('provenance_id_preservation_rate'))}</div>
</div>
"""
    return _page("DefeatWatermarker attack report", verification.evidence_id, body)


def _benchmark_html(payload: dict[str, Any]) -> str:
    verification = verify_benchmark_document(payload)
    if (
        not verification.valid
        or verification.report_id is None
        or verification.benchmark_type is None
    ):
        raise ReportError("benchmark evidence failed integrity verification")

    if verification.benchmark_type == "reliability":
        summary = payload["summary"]
        rows = []
        for case in payload["cases"]:
            rows.append(
                "<tr>"
                f"<td>{_escape(case.get('case_id'))}</td>"
                f"<td>{_bool(case.get('expected_detected'))}</td>"
                f"<td>{_bool(case.get('actual_detected'))}</td>"
                f"<td>{_escape(case.get('confidence'))}</td>"
                f"<td>{_escape(case.get('verification_state'))}</td>"
                "</tr>"
            )
        body = f"""
<h2>Benchmark</h2>
<div class="meta">
<div>Corpus</div><div>{_escape(payload.get('corpus_id'))} {_escape(payload.get('corpus_version'))}</div>
<div>Adapter</div><div><code>{_escape(payload.get('adapter_id'))}</code></div>
<div>Cases</div><div>{len(payload.get('cases', []))}</div>
<div>Accuracy</div><div>{_percent(summary.get('accuracy'))}</div>
<div>Precision</div><div>{_percent(summary.get('precision'))}</div>
<div>Recall</div><div>{_percent(summary.get('recall'))}</div>
<div>Specificity</div><div>{_percent(summary.get('specificity'))}</div>
<div>False-positive rate</div><div>{_percent(summary.get('false_positive_rate'))}</div>
<div>False-negative rate</div><div>{_percent(summary.get('false_negative_rate'))}</div>
</div>
<h2>Labelled cases</h2>
<table><thead><tr><th>Case</th><th>Expected</th><th>Actual</th><th>Confidence</th><th>Verification</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
"""
        return _page(
            "DefeatWatermarker reliability benchmark report",
            verification.report_id,
            body,
        )

    pair_rows = []
    for pair in payload["pairs"]:
        pair_rows.append(
            "<tr>"
            f"<td><code>{_escape(pair.get('left_adapter_id'))}</code></td>"
            f"<td><code>{_escape(pair.get('right_adapter_id'))}</code></td>"
            f"<td>{_escape(pair.get('comparable_cases'))}</td>"
            f"<td>{_escape(pair.get('detection_agreements'))}</td>"
            f"<td>{_escape(pair.get('detection_disagreements'))}</td>"
            f"<td>{_percent(pair.get('agreement_rate'))}</td>"
            "</tr>"
        )
    body = f"""
<h2>Benchmark</h2>
<div class="meta">
<div>Matrix</div><div>{_escape(payload.get('matrix_id'))} {_escape(payload.get('matrix_version'))}</div>
<div>Adapters</div><div>{len(payload.get('adapter_runtime', {}))}</div>
<div>Cases</div><div>{len(payload.get('cases', []))}</div>
</div>
<h2>Pairwise agreement</h2>
<table><thead><tr><th>Left adapter</th><th>Right adapter</th><th>Comparable</th><th>Agreements</th><th>Disagreements</th><th>Agreement rate</th></tr></thead>
<tbody>{''.join(pair_rows)}</tbody></table>
"""
    return _page(
        "DefeatWatermarker interoperability benchmark report",
        verification.report_id,
        body,
    )


def _batch_html(directory: Path) -> str:
    verification = verify_batch_directory(directory)
    if not verification.valid or verification.batch_id is None:
        raise ReportError("batch directory failed integrity verification")
    payload = json.loads((directory / "batch.json").read_text(encoding="utf-8"))
    rows = []
    for record in payload.get("records", []):
        rows.append(
            "<tr>"
            f"<td>{_escape(record.get('relative_path'))}</td>"
            f"<td>{_escape(record.get('modality'))}</td>"
            f"<td>{_escape(record.get('mode'))}</td>"
            f"<td><code>{_escape(record.get('record_id'))}</code></td>"
            f"<td>{_escape(record.get('error'))}</td>"
            "</tr>"
        )
    body = f"""
<h2>Batch</h2>
<div class="meta">
<div>Input name</div><div>{_escape(payload.get('input_name'))}</div>
<div>Recursive</div><div>{_bool(payload.get('recursive'))}</div>
<div>Scan only</div><div>{_bool(payload.get('scan_only'))}</div>
<div>Records</div><div>{len(payload.get('records', []))}</div>
</div>
<h2>Artifacts</h2>
<table><thead><tr><th>Artifact</th><th>Modality</th><th>Mode</th><th>Record ID</th><th>Error</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
"""
    return _page("DefeatWatermarker batch report", verification.batch_id, body)


def render_report(input_path: Path) -> str:
    if input_path.is_dir():
        try:
            return _batch_html(input_path)
        except (
            BatchVerificationError,
            OSError,
            UnicodeError,
            json.JSONDecodeError,
        ) as exc:
            raise ReportError(str(exc)) from exc

    try:
        payload = load_evidence_document(input_path)
    except EvidenceError:
        try:
            payload = load_scan_document(input_path)
        except ScanEvidenceError as exc:
            raise ReportError(str(exc)) from exc

    if "evidence_id" in payload:
        return _evaluation_html(payload)
    if "scan_id" in payload:
        return _scan_html(payload)
    if "report_id" in payload:
        return _benchmark_html(payload)
    raise ReportError(
        "input is not recognized scan, evaluation, or benchmark evidence"
    )
