from __future__ import annotations

import json
from pathlib import Path

from defeat_watermarker.builtin_suites import builtin_suite_catalog, builtin_suite_for
from defeat_watermarker.models import Modality
from defeat_watermarker.ui_cli import main


def test_builtin_suite_catalog_covers_primary_modalities() -> None:
    catalog = builtin_suite_catalog()
    ids = {suite.suite_id for suite in catalog}
    assert ids == {
        "image-platform-rendition",
        "audio-pcm-workflow",
        "video-platform-rendition",
        "text-editorial-normalization",
    }
    assert builtin_suite_for(Modality.DOCUMENT) is None


def test_ui_scan_only_prints_detector_output(tmp_path: Path, capsys) -> None:
    artifact = tmp_path / "sample.txt"
    artifact.write_text("hello provenance\n", encoding="utf-8")

    assert main([str(artifact), "--media-type", "text/plain", "--scan-only"]) == 0
    output = capsys.readouterr().out
    assert "DefeatWatermarker — anti-watermark console" in output
    assert "Detector/model output" in output
    assert "scan only" in output


def test_ui_runs_builtin_text_attack_and_writes_evidence(tmp_path: Path, capsys) -> None:
    artifact = tmp_path / "sample.txt"
    artifact.write_bytes(b"Cafe\xcc\x81  \r\nsecond line\t\r\n")
    evidence_path = tmp_path / "evidence.json"

    assert (
        main(
            [
                str(artifact),
                "--media-type",
                "text/plain",
                "--json-output",
                str(evidence_path),
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert "Anti-watermark attack results" in output
    assert "unicode-nfc" in output
    assert "Evidence ID:" in output

    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert isinstance(payload["evidence_id"], str)
    assert len(payload["evidence_id"]) == 64
    assert payload["suite"]["suite_id"] == "text-editorial-normalization"
    assert "artifact_bytes" not in payload


def test_ui_lists_builtin_suites(capsys) -> None:
    assert main(["--list-builtins"]) == 0
    output = capsys.readouterr().out
    assert "image-platform-rendition" in output
    assert "text-editorial-normalization" in output
