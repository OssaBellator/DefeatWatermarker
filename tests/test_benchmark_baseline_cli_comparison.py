from __future__ import annotations

import json
from pathlib import Path

from defeat_watermarker.adapters.base import WatermarkAdapter
from defeat_watermarker.benchmark_baseline_cli import main
from defeat_watermarker.models import Artifact, DetectionResult, MarkFamily, Modality
from defeat_watermarker.registry import AdapterRegistry
from defeat_watermarker.reliability import run_reliability_benchmark


class FixtureAdapter(WatermarkAdapter):
    adapter_id = "fixture.baseline-cli.v1"
    family = MarkFamily.UNKNOWN
    modalities = frozenset({Modality.TEXT})

    def detect(self, artifact: Artifact) -> DetectionResult:
        detected = b"marker" in artifact.data
        return DetectionResult(
            adapter_id=self.adapter_id,
            family=self.family,
            detected=detected,
            confidence=1.0 if detected else 0.0,
        )


def _report_file(tmp_path: Path) -> Path:
    corpus = tmp_path / "corpus.json"
    corpus.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "corpus_id": "cli-comparison",
                "version": "0.1",
                "adapter_id": "fixture.baseline-cli.v1",
                "description": "fixture",
                "cases": [
                    {
                        "case_id": "positive",
                        "path": "positive.txt",
                        "media_type": "text/plain",
                        "modality": "text",
                        "expected_detected": True
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "positive.txt").write_text("marker", encoding="utf-8")
    report = run_reliability_benchmark(
        corpus,
        AdapterRegistry([FixtureAdapter()]),
    ).to_dict()
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    return path


def test_baseline_compare_output_is_independently_verifiable(tmp_path: Path, capsys) -> None:
    report = _report_file(tmp_path)
    baseline = tmp_path / "baseline.json"
    comparison = tmp_path / "comparison.json"

    assert main(["create", str(report), "--output", str(baseline)]) == 0
    capsys.readouterr()
    assert (
        main(
            [
                "compare",
                str(report),
                "--baseline",
                str(baseline),
                "--output",
                str(comparison),
            ]
        )
        == 0
    )
    capsys.readouterr()

    payload = json.loads(comparison.read_text(encoding="utf-8"))
    assert payload["status"] == "same_or_better"
    assert len(payload["comparison_id"]) == 64

    assert main(["verify-comparison", str(comparison)]) == 0
    verification = json.loads(capsys.readouterr().out)
    assert verification["valid"] is True
    assert verification["comparison_id"] == payload["comparison_id"]
