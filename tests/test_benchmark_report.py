from __future__ import annotations

import json
from pathlib import Path

import pytest

from defeat_watermarker.adapters.base import WatermarkAdapter
from defeat_watermarker.interoperability import run_interoperability_matrix
from defeat_watermarker.models import Artifact, DetectionResult, MarkFamily, Modality
from defeat_watermarker.registry import AdapterRegistry
from defeat_watermarker.reliability import run_reliability_benchmark
from defeat_watermarker.report import ReportError, render_report


class MarkerAdapter(WatermarkAdapter):
    family = MarkFamily.UNKNOWN
    modalities = frozenset({Modality.TEXT})

    def __init__(self, adapter_id: str, marker: bytes) -> None:
        self.adapter_id = adapter_id
        self.marker = marker

    def detect(self, artifact: Artifact) -> DetectionResult:
        found = self.marker in artifact.data
        return DetectionResult(
            adapter_id=self.adapter_id,
            family=self.family,
            detected=found,
            confidence=1.0 if found else 0.0,
        )


def test_reliability_report_renders_verified_html(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.json"
    corpus.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "corpus_id": "report-reliability",
                "version": "0.1",
                "adapter_id": "fixture.primary",
                "description": "fixture",
                "cases": [
                    {
                        "case_id": "positive",
                        "path": "positive.txt",
                        "media_type": "text/plain",
                        "modality": "text",
                        "expected_detected": True,
                    },
                    {
                        "case_id": "negative",
                        "path": "negative.txt",
                        "media_type": "text/plain",
                        "modality": "text",
                        "expected_detected": False,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "positive.txt").write_bytes(b"marker")
    (tmp_path / "negative.txt").write_bytes(b"plain")
    report = run_reliability_benchmark(
        corpus,
        AdapterRegistry([MarkerAdapter("fixture.primary", b"marker")]),
    )
    path = tmp_path / "reliability.json"
    path.write_text(json.dumps(report.to_dict()), encoding="utf-8")

    rendered = render_report(path)

    assert "DefeatWatermarker reliability report" in rendered
    assert "True positive" in rendered
    assert "100.0%" in rendered
    assert report.report_id in rendered
    assert "marker" not in rendered


def test_interoperability_report_renders_pairwise_html(tmp_path: Path) -> None:
    matrix = tmp_path / "matrix.json"
    matrix.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "matrix_id": "report-interoperability",
                "version": "0.1",
                "description": "fixture",
                "adapter_ids": ["fixture.left", "fixture.right"],
                "cases": [
                    {
                        "case_id": "case",
                        "path": "case.txt",
                        "media_type": "text/plain",
                        "modality": "text",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "case.txt").write_bytes(b"left right")
    report = run_interoperability_matrix(
        matrix,
        AdapterRegistry(
            [
                MarkerAdapter("fixture.left", b"left"),
                MarkerAdapter("fixture.right", b"right"),
            ]
        ),
    )
    path = tmp_path / "interoperability.json"
    path.write_text(json.dumps(report.to_dict()), encoding="utf-8")

    rendered = render_report(path)

    assert "DefeatWatermarker interoperability report" in rendered
    assert "Pairwise detector agreement" in rendered
    assert "fixture.left" in rendered
    assert "fixture.right" in rendered
    assert report.report_id in rendered
    assert "left right" not in rendered


def test_tampered_benchmark_report_is_not_rendered(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.json"
    corpus.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "corpus_id": "tamper",
                "version": "0.1",
                "adapter_id": "fixture.primary",
                "description": "fixture",
                "cases": [
                    {
                        "case_id": "case",
                        "path": "case.txt",
                        "media_type": "text/plain",
                        "modality": "text",
                        "expected_detected": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "case.txt").write_bytes(b"marker")
    report = run_reliability_benchmark(
        corpus,
        AdapterRegistry([MarkerAdapter("fixture.primary", b"marker")]),
    ).to_dict()
    report["summary"]["accuracy"] = 0.0
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ReportError, match="failed integrity verification"):
        render_report(path)
