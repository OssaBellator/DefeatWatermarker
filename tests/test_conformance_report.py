from __future__ import annotations

import json
from pathlib import Path

from defeat_watermarker.adapters.base import WatermarkAdapter
from defeat_watermarker.detector_conformance import run_detector_conformance
from defeat_watermarker.models import Artifact, DetectionResult, MarkFamily, Modality
from defeat_watermarker.report import render_report


class ConformanceReportAdapter(WatermarkAdapter):
    adapter_id = "fixture.conformance-report.v1"
    family = MarkFamily.UNKNOWN
    modalities = frozenset({Modality.TEXT})

    def runtime_identity(self):
        return ("profile=<script>fixture-v1",)

    def detect(self, artifact: Artifact) -> DetectionResult:
        return DetectionResult(
            adapter_id=self.adapter_id,
            family=self.family,
            detected=True,
            confidence=0.8,
        )


def test_conformance_report_is_verified_static_html(tmp_path: Path) -> None:
    artifact = Artifact(
        data=b"detector conformance fixture",
        media_type="text/plain",
        name="fixture.txt",
        modality=Modality.TEXT,
    )
    payload = run_detector_conformance(
        "fixture<script>", ConformanceReportAdapter(), artifact
    ).to_dict()
    source = tmp_path / "conformance.json"
    source.write_text(json.dumps(payload), encoding="utf-8")

    rendered = render_report(source)

    assert "DefeatWatermarker detector conformance report" in rendered
    assert "read_only_capability" in rendered
    assert "&lt;script&gt;" in rendered
    assert "<script" not in rendered
    assert "http://" not in rendered
    assert "https://" not in rendered
    assert "detector conformance fixture" not in rendered
