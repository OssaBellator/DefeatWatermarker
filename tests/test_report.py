from __future__ import annotations

import json
from pathlib import Path

from defeat_watermarker.adapters.base import WatermarkAdapter
from defeat_watermarker.batch_cli import main as batch_main
from defeat_watermarker.builtin_suites import builtin_suite_for
from defeat_watermarker.cli import _mutations
from defeat_watermarker.digests import content_digest
from defeat_watermarker.engine import RobustnessEngine
from defeat_watermarker.evidence import build_evidence_bundle
from defeat_watermarker.metrics import summarize_report
from defeat_watermarker.models import Artifact, DetectionResult, MarkFamily, Modality
from defeat_watermarker.registry import AdapterRegistry
from defeat_watermarker.report import render_report
from defeat_watermarker.report_cli import main as report_main
from defeat_watermarker.scan_evidence import build_scan_evidence


class ReportAdapter(WatermarkAdapter):
    adapter_id = "test.report.v1"
    family = MarkFamily.UNKNOWN
    modalities = frozenset({Modality.TEXT})

    def detect(self, artifact: Artifact) -> DetectionResult:
        return DetectionResult(
            adapter_id=self.adapter_id,
            family=self.family,
            detected=True,
            confidence=0.8,
        )


def _bind_report(core: dict[str, object]) -> dict[str, object]:
    return {"report_id": content_digest(core), **core}


def _reliability_report() -> dict[str, object]:
    return _bind_report(
        {
            "schema_version": "0.2",
            "corpus_id": "report-fixture",
            "corpus_version": "0.1",
            "corpus_digest": "a" * 64,
            "adapter_id": "fixture.report.v1",
            "adapter_runtime": ["adapter_id=fixture.report.v1"],
            "cases": [
                {
                    "case_id": "positive<script>",
                    "artifact_sha256": "b" * 64,
                    "byte_length": 10,
                    "expected_detected": True,
                    "actual_detected": True,
                    "confidence": 1.0,
                    "verification_state": "not_evaluated",
                },
                {
                    "case_id": "negative",
                    "artifact_sha256": "c" * 64,
                    "byte_length": 9,
                    "expected_detected": False,
                    "actual_detected": False,
                    "confidence": 0.0,
                    "verification_state": "not_evaluated",
                },
            ],
            "summary": {
                "true_positive": 1,
                "true_negative": 1,
                "false_positive": 0,
                "false_negative": 0,
                "accuracy": 1.0,
                "precision": 1.0,
                "recall": 1.0,
                "specificity": 1.0,
                "false_positive_rate": 0.0,
                "false_negative_rate": 0.0,
            },
        }
    )


def _interoperability_report() -> dict[str, object]:
    return _bind_report(
        {
            "schema_version": "0.2",
            "matrix_id": "report-matrix",
            "matrix_version": "0.1",
            "matrix_digest": "d" * 64,
            "adapter_runtime": {
                "left": ["adapter_id=left"],
                "right": ["adapter_id=right"],
            },
            "cases": [
                {
                    "case_id": "case",
                    "artifact_sha256": "e" * 64,
                    "byte_length": 5,
                    "observations": [
                        {
                            "adapter_id": "left",
                            "supported": True,
                            "family": "unknown",
                            "detected": True,
                            "confidence": 1.0,
                            "verification_state": "not_evaluated",
                            "provenance_identifier": None,
                        },
                        {
                            "adapter_id": "right",
                            "supported": True,
                            "family": "unknown",
                            "detected": False,
                            "confidence": 0.0,
                            "verification_state": "not_evaluated",
                            "provenance_identifier": None,
                        },
                    ],
                }
            ],
            "pairs": [
                {
                    "left_adapter_id": "left",
                    "right_adapter_id": "right",
                    "comparable_cases": 1,
                    "detection_agreements": 0,
                    "detection_disagreements": 1,
                    "agreement_rate": 0.0,
                    "both_detected": 0,
                    "both_not_detected": 0,
                }
            ],
        }
    )


def test_scan_report_verifies_and_escapes_artifact_name(tmp_path: Path) -> None:
    artifact = Artifact(
        data=b"private scan bytes",
        media_type="text/plain",
        name="<img src=x onerror=alert(1)>.txt",
        modality=Modality.TEXT,
    )
    scan = build_scan_evidence(artifact, AdapterRegistry([ReportAdapter()]))
    path = tmp_path / "scan.json"
    path.write_text(json.dumps(scan.to_dict()), encoding="utf-8")

    rendered = render_report(path)

    assert "&lt;img src=x onerror=alert(1)&gt;.txt" in rendered
    assert "<img src=x onerror=alert(1)>" not in rendered
    assert "private scan bytes" not in rendered
    assert scan.scan_id in rendered


def test_attack_report_renders_verified_summary_without_artifact_bytes(tmp_path: Path) -> None:
    artifact = Artifact(
        data=b"Example editorial fixture  \r\n",
        media_type="text/plain",
        name="fixture.txt",
        modality=Modality.TEXT,
    )
    suite = builtin_suite_for(Modality.TEXT)
    assert suite is not None
    report = RobustnessEngine(AdapterRegistry([ReportAdapter()]), _mutations()).evaluate(
        artifact, suite.scenarios
    )
    evidence = build_evidence_bundle(artifact, suite, report, summarize_report(report))
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(evidence.to_dict()), encoding="utf-8")

    rendered = render_report(path)

    assert "DefeatWatermarker attack report" in rendered
    assert "Fixed anti-watermark attack results" in rendered
    assert "test.report.v1" in rendered
    assert evidence.evidence_id in rendered
    assert "Example editorial fixture" not in rendered


def test_batch_report_requires_and_renders_verified_batch(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    (inputs / "unknown.bin").write_bytes(b"opaque fixture")
    output = tmp_path / "batch"
    assert batch_main([str(inputs), "--scan-only", "--output-dir", str(output)]) == 0

    rendered = render_report(output)

    assert "DefeatWatermarker batch report" in rendered
    assert "unknown.bin" in rendered
    assert "scan" in rendered
    assert "opaque fixture" not in rendered


def test_reliability_benchmark_report_is_verified_static_html(tmp_path: Path) -> None:
    payload = _reliability_report()
    path = tmp_path / "reliability.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    rendered = render_report(path)

    assert "DefeatWatermarker reliability benchmark report" in rendered
    assert "100.0%" in rendered
    assert "&lt;script&gt;" in rendered
    assert "positive<script>" not in rendered
    assert "<script" not in rendered
    assert "http://" not in rendered
    assert "https://" not in rendered


def test_interoperability_benchmark_report_is_verified_static_html(tmp_path: Path) -> None:
    payload = _interoperability_report()
    path = tmp_path / "interoperability.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    rendered = render_report(path)

    assert "DefeatWatermarker interoperability benchmark report" in rendered
    assert "0.0%" in rendered
    assert "left" in rendered and "right" in rendered
    assert "<script" not in rendered
    assert "http://" not in rendered
    assert "https://" not in rendered


def test_report_cli_writes_self_contained_html(tmp_path: Path, capsys) -> None:
    artifact = Artifact(
        data=b"fixture",
        media_type="text/plain",
        name="fixture.txt",
        modality=Modality.TEXT,
    )
    scan = build_scan_evidence(artifact, AdapterRegistry([ReportAdapter()]))
    source = tmp_path / "scan.json"
    source.write_text(json.dumps(scan.to_dict()), encoding="utf-8")
    output = tmp_path / "report.html"

    assert report_main([str(source), "--output", str(output)]) == 0
    assert "HTML report:" in capsys.readouterr().out
    rendered = output.read_text(encoding="utf-8")
    assert "<!doctype html>" in rendered
    assert "<script" not in rendered
    assert "http://" not in rendered
    assert "https://" not in rendered
