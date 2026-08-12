import json

from defeat_watermarker.adapters.base import WatermarkAdapter
from defeat_watermarker.interoperability import run_interoperability_matrix
from defeat_watermarker.models import Artifact, DetectionResult, MarkFamily, Modality
from defeat_watermarker.registry import AdapterRegistry


class KeywordAdapter(WatermarkAdapter):
    family = MarkFamily.PERCEPTUAL
    modalities = frozenset({Modality.UNKNOWN})

    def __init__(self, adapter_id: str, keyword: bytes) -> None:
        self.adapter_id = adapter_id
        self.keyword = keyword

    def detect(self, artifact: Artifact) -> DetectionResult:
        found = self.keyword in artifact.data
        return DetectionResult(
            adapter_id=self.adapter_id,
            family=self.family,
            detected=found,
            confidence=1.0 if found else 0.0,
        )


def test_pairwise_matrix_reports_agreement_without_artifact_bytes(tmp_path) -> None:
    payload = {
        "schema_version": "0.1",
        "matrix_id": "fixture",
        "version": "0.1",
        "description": "fixture",
        "adapter_ids": ["left", "right"],
        "cases": [
            {
                "case_id": "positive",
                "path": "positive.dat",
                "media_type": "application/octet-stream",
                "modality": "unknown",
            },
            {
                "case_id": "negative",
                "path": "negative.dat",
                "media_type": "application/octet-stream",
                "modality": "unknown",
            },
        ],
    }
    matrix_path = tmp_path / "matrix.json"
    matrix_path.write_text(json.dumps(payload), encoding="utf-8")
    (tmp_path / "positive.dat").write_bytes(b"alpha beta")
    (tmp_path / "negative.dat").write_bytes(b"plain")

    report = run_interoperability_matrix(
        matrix_path,
        AdapterRegistry(
            [KeywordAdapter("left", b"alpha"), KeywordAdapter("right", b"beta")]
        ),
    )
    pair = report.pairs[0]
    assert pair.comparable_cases == 2
    assert pair.agreement_rate == 1.0
    assert pair.both_detected == 1
    assert pair.both_not_detected == 1
    assert "alpha beta" not in repr(report.to_dict())
    assert len(report.report_id) == 64


def test_pairwise_matrix_surfaces_disagreement(tmp_path) -> None:
    payload = {
        "schema_version": "0.1",
        "matrix_id": "fixture",
        "version": "0.1",
        "description": "fixture",
        "adapter_ids": ["left", "right"],
        "cases": [
            {
                "case_id": "case",
                "path": "case.dat",
                "media_type": "application/octet-stream",
                "modality": "unknown",
            }
        ],
    }
    matrix_path = tmp_path / "matrix.json"
    matrix_path.write_text(json.dumps(payload), encoding="utf-8")
    (tmp_path / "case.dat").write_bytes(b"alpha")

    report = run_interoperability_matrix(
        matrix_path,
        AdapterRegistry(
            [KeywordAdapter("left", b"alpha"), KeywordAdapter("right", b"beta")]
        ),
    )
    assert report.pairs[0].agreement_rate == 0.0
    assert report.pairs[0].detection_disagreements == 1
