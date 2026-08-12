from __future__ import annotations

import json
from pathlib import Path

from defeat_watermarker.adapters.base import WatermarkAdapter
from defeat_watermarker.models import Artifact, DetectionResult, MarkFamily, Modality
from defeat_watermarker.registry import AdapterRegistry
from defeat_watermarker.scan_cli import main
from defeat_watermarker.scan_evidence import build_scan_evidence, verify_scan_document


class ScanCliAdapter(WatermarkAdapter):
    adapter_id = "test.scan-cli.v1"
    family = MarkFamily.UNKNOWN
    modalities = frozenset({Modality.TEXT})

    def detect(self, artifact: Artifact) -> DetectionResult:
        return DetectionResult(
            adapter_id=self.adapter_id,
            family=self.family,
            detected=True,
            confidence=0.75,
        )


def _scan_payload() -> dict[str, object]:
    artifact = Artifact(
        data=b"fixture text",
        media_type="text/plain",
        name="fixture.txt",
        modality=Modality.TEXT,
    )
    return build_scan_evidence(artifact, AdapterRegistry([ScanCliAdapter()])).to_dict()


def test_scan_verifier_accepts_valid_document(tmp_path: Path, capsys) -> None:
    path = tmp_path / "scan.json"
    path.write_text(json.dumps(_scan_payload()), encoding="utf-8")

    assert main([str(path)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["valid"] is True
    assert "scan_id" in output["checks"]


def test_scan_verifier_detects_modified_model_output() -> None:
    payload = _scan_payload()
    payload["results"][0]["confidence"] = 0.01

    result = verify_scan_document(payload)

    assert result.valid is False
    assert any("scan_id does not match" in error for error in result.errors)


def test_scan_verifier_cli_returns_nonzero_for_tampered_document(
    tmp_path: Path, capsys
) -> None:
    payload = _scan_payload()
    payload["artifact"]["byte_length"] += 1
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert main([str(path)]) == 4
    output = json.loads(capsys.readouterr().out)
    assert output["valid"] is False
