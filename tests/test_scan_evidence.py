from __future__ import annotations

import pytest

from defeat_watermarker.adapters.base import WatermarkAdapter
from defeat_watermarker.models import Artifact, DetectionResult, MarkFamily, Modality
from defeat_watermarker.registry import AdapterRegistry
from defeat_watermarker.scan_evidence import build_scan_evidence


class ScanFixtureAdapter(WatermarkAdapter):
    adapter_id = "test.scan.v1"
    family = MarkFamily.UNKNOWN
    modalities = frozenset({Modality.TEXT})

    def detect(self, artifact: Artifact) -> DetectionResult:
        return DetectionResult(
            adapter_id=self.adapter_id,
            family=self.family,
            detected=b"marker" in artifact.data,
            confidence=1.0 if b"marker" in artifact.data else 0.0,
        )


class MismatchedResultAdapter(ScanFixtureAdapter):
    adapter_id = "test.scan-bad.v1"

    def detect(self, artifact: Artifact) -> DetectionResult:
        return DetectionResult(
            adapter_id="different.adapter.v1",
            family=self.family,
            detected=True,
            confidence=1.0,
        )


def test_scan_evidence_is_content_addressed_and_byte_free() -> None:
    artifact = Artifact(
        data=b"fixture marker text",
        media_type="text/plain",
        name="fixture.txt",
        modality=Modality.TEXT,
    )
    scan = build_scan_evidence(artifact, AdapterRegistry([ScanFixtureAdapter()]))
    payload = scan.to_dict()

    assert len(scan.scan_id) == 64
    assert payload["artifact"]["name"] == "fixture.txt"
    assert payload["artifact"]["byte_length"] == len(artifact.data)
    assert len(payload["artifact"]["sha256"]) == 64
    assert payload["results"][0]["detected"] is True
    assert "data" not in payload["artifact"]
    assert "test.scan.v1" in payload["adapter_runtime"]


def test_same_scan_input_and_runtime_produce_same_scan_id() -> None:
    artifact = Artifact(
        data=b"fixture marker text",
        media_type="text/plain",
        name="fixture.txt",
        modality=Modality.TEXT,
    )

    first = build_scan_evidence(artifact, AdapterRegistry([ScanFixtureAdapter()]))
    second = build_scan_evidence(artifact, AdapterRegistry([ScanFixtureAdapter()]))

    assert first.scan_id == second.scan_id


def test_scan_rejects_adapter_result_id_mismatch() -> None:
    artifact = Artifact(
        data=b"marker",
        media_type="text/plain",
        name="fixture.txt",
        modality=Modality.TEXT,
    )

    with pytest.raises(ValueError, match="mismatched result id"):
        build_scan_evidence(artifact, AdapterRegistry([MismatchedResultAdapter()]))
