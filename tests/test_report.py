from __future__ import annotations

import json
from pathlib import Path

from defeat_watermarker.adapters.base import WatermarkAdapter
from defeat_watermarker.batch_cli import main as batch_main
from defeat_watermarker.builtin_suites import builtin_suite_for
from defeat_watermarker.cli import _mutations
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


def test_scan_report_verifies_and_escapes_artifact_name(tmp_path: Path) -> None:
    artifact = Artifact(
        data=b"private scan bytes",
        media_type="text/plain",
        name="<script>alert(1)</script>.txt",
        modality=Modality.TEXT,
    )
    scan = build_scan_evidence(artifact, AdapterRegistry([ReportAdapter()]))
    path = tmp_path / "scan.json"
    path.write_text(json.dumps(scan.to_dict()), encoding="utf-8")

    rendered = render_report(path)

    assert "&lt;script&gt;alert(1)&lt;/script&gt;.txt" in rendered
    assert "<script>alert(1)</script>" not in rendered
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
