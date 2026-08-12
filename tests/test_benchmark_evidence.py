from __future__ import annotations

import json
from pathlib import Path

from defeat_watermarker.adapters.base import WatermarkAdapter
from defeat_watermarker.benchmark_evidence import verify_benchmark_document
from defeat_watermarker.benchmark_verify_cli import main as benchmark_verify_main
from defeat_watermarker.interoperability import run_interoperability_matrix
from defeat_watermarker.models import Artifact, DetectionResult, MarkFamily, Modality
from defeat_watermarker.registry import AdapterRegistry
from defeat_watermarker.reliability import run_reliability_benchmark


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


def _reliability_payload(tmp_path: Path) -> dict[str, object]:
    corpus = tmp_path / "corpus.json"
    corpus.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "corpus_id": "fixture",
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
    return report.to_dict()


def _interoperability_payload(tmp_path: Path) -> dict[str, object]:
    matrix = tmp_path / "matrix.json"
    matrix.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "matrix_id": "fixture-matrix",
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
    return report.to_dict()


def test_reliability_report_verifies_offline(tmp_path: Path) -> None:
    result = verify_benchmark_document(_reliability_payload(tmp_path))

    assert result.valid is True
    assert result.benchmark_type == "reliability"
    assert "report_id" in result.checks


def test_reliability_tamper_invalidates_report_id(tmp_path: Path) -> None:
    payload = _reliability_payload(tmp_path)
    payload["summary"]["true_positive"] = 99

    result = verify_benchmark_document(payload)

    assert result.valid is False
    assert any("report_id does not match" in error for error in result.errors)


def test_interoperability_report_verifies_offline(tmp_path: Path) -> None:
    result = verify_benchmark_document(_interoperability_payload(tmp_path))

    assert result.valid is True
    assert result.benchmark_type == "interoperability"
    assert "pairs" in result.checks


def test_interoperability_tamper_invalidates_report_id(tmp_path: Path) -> None:
    payload = _interoperability_payload(tmp_path)
    payload["pairs"][0]["agreement_rate"] = 0.0

    result = verify_benchmark_document(payload)

    assert result.valid is False
    assert any("report_id does not match" in error for error in result.errors)


def test_benchmark_verifier_cli_accepts_valid_report(tmp_path: Path, capsys) -> None:
    payload = _reliability_payload(tmp_path)
    path = tmp_path / "report.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert benchmark_verify_main([str(path)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["valid"] is True
    assert output["benchmark_type"] == "reliability"
