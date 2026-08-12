from __future__ import annotations

import json
from pathlib import Path

from defeat_watermarker.adapters.base import WatermarkAdapter
from defeat_watermarker.cli import _scan, build_parser
from defeat_watermarker.models import Artifact, DetectionResult, MarkFamily, Modality


class CliFixtureAdapter(WatermarkAdapter):
    adapter_id = "test.cli-plugin.v1"
    family = MarkFamily.UNKNOWN
    modalities = frozenset({Modality.TEXT})

    def detect(self, artifact: Artifact) -> DetectionResult:
        detected = b"fixture" in artifact.data
        return DetectionResult(
            adapter_id=self.adapter_id,
            family=self.family,
            detected=detected,
            confidence=1.0 if detected else 0.0,
        )


def test_scan_parser_accepts_repeatable_detector_plugin() -> None:
    args = build_parser().parse_args(
        [
            "scan",
            "fixture.txt",
            "--detector-plugin",
            "one",
            "--detector-plugin",
            "two",
        ]
    )

    assert args.detector_plugin == ["one", "two"]


def test_evaluate_parser_accepts_detector_plugin() -> None:
    args = build_parser().parse_args(
        [
            "evaluate",
            "fixture.txt",
            "--suite",
            "suite.json",
            "--detector-plugin",
            "provider-text",
        ]
    )

    assert args.detector_plugin == ["provider-text"]


def test_reliability_parser_accepts_detector_plugin() -> None:
    args = build_parser().parse_args(
        [
            "benchmark",
            "reliability",
            "corpus.json",
            "--detector-plugin",
            "provider-text",
        ]
    )

    assert args.detector_plugin == ["provider-text"]


def test_interoperability_parser_accepts_repeatable_detector_plugins() -> None:
    args = build_parser().parse_args(
        [
            "benchmark",
            "interoperability",
            "matrix.json",
            "--detector-plugin",
            "provider-one",
            "--detector-plugin",
            "provider-two",
        ]
    )

    assert args.detector_plugin == ["provider-one", "provider-two"]


def test_scan_uses_explicit_detector_plugin(monkeypatch, tmp_path: Path) -> None:
    artifact_path = tmp_path / "fixture.txt"
    artifact_path.write_text("fixture text", encoding="utf-8")
    output = tmp_path / "scan.json"
    requested: list[tuple[str, ...]] = []

    def fake_load(names):
        requested.append(tuple(names))
        return (CliFixtureAdapter(),)

    monkeypatch.setattr("defeat_watermarker.cli.load_detector_plugins", fake_load)
    monkeypatch.setattr(
        "defeat_watermarker.cli.C2paPythonBackend.available",
        staticmethod(lambda: False),
    )

    assert _scan(
        artifact_path,
        "text/plain",
        output,
        None,
        ("provider-text",),
    ) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    by_id = {item["adapter_id"]: item for item in payload["results"]}
    assert requested == [("provider-text",)]
    assert by_id["test.cli-plugin.v1"]["detected"] is True
