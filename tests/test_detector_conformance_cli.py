from __future__ import annotations

import json
from pathlib import Path

from defeat_watermarker.adapters.base import WatermarkAdapter
from defeat_watermarker.detector_conformance_cli import main as conformance_main
from defeat_watermarker.models import DetectionResult, MarkFamily, Modality


class GoodCliAdapter(WatermarkAdapter):
    adapter_id = "fixture.conformance-cli.good.v1"
    family = MarkFamily.UNKNOWN
    modalities = frozenset({Modality.TEXT})

    def runtime_identity(self):
        return ("model=cli-fixture-v1",)

    def detect(self, artifact):
        return DetectionResult(
            adapter_id=self.adapter_id,
            family=self.family,
            detected=True,
            confidence=0.8,
        )


class BadCliAdapter(GoodCliAdapter):
    adapter_id = "fixture.conformance-cli.bad.v1"

    def remove(self, artifact):
        return artifact


def test_conformance_cli_run_and_verify(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(
        "defeat_watermarker.detector_conformance_cli.load_detector_plugins",
        lambda names: (GoodCliAdapter(),),
    )
    source = tmp_path / "fixture.txt"
    source.write_text("fixture", encoding="utf-8")
    output = tmp_path / "conformance.json"

    assert (
        conformance_main(
            [
                "run",
                str(source),
                "--media-type",
                "text/plain",
                "--detector-plugin",
                "fixture-good",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["passed"] is True
    assert payload["adapter_id"] == GoodCliAdapter.adapter_id

    assert conformance_main(["verify", str(output)]) == 0
    verification = json.loads(capsys.readouterr().out)
    assert verification["valid"] is True


def test_conformance_cli_returns_two_for_nonconforming_adapter(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "defeat_watermarker.detector_conformance_cli.load_detector_plugins",
        lambda names: (BadCliAdapter(),),
    )
    source = tmp_path / "fixture.txt"
    source.write_text("fixture", encoding="utf-8")

    assert (
        conformance_main(
            [
                "run",
                str(source),
                "--media-type",
                "text/plain",
                "--detector-plugin",
                "fixture-bad",
            ]
        )
        == 2
    )
