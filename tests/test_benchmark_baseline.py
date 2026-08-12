from __future__ import annotations

import json
from pathlib import Path

from defeat_watermarker.adapters.base import WatermarkAdapter
from defeat_watermarker.benchmark_baseline import (
    BenchmarkBaselineError,
    BenchmarkComparisonStatus,
    baseline_from_dict,
    compare_benchmark_to_baseline,
    create_benchmark_baseline,
)
from defeat_watermarker.benchmark_baseline_cli import main as baseline_cli_main
from defeat_watermarker.digests import content_digest
from defeat_watermarker.models import Artifact, DetectionResult, MarkFamily, Modality
from defeat_watermarker.registry import AdapterRegistry
from defeat_watermarker.reliability import run_reliability_benchmark


class MarkerAdapter(WatermarkAdapter):
    adapter_id = "fixture.baseline.v1"
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


def _report(tmp_path: Path) -> dict[str, object]:
    corpus = tmp_path / "corpus.json"
    corpus.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "corpus_id": "baseline-fixture",
                "version": "0.1",
                "adapter_id": "fixture.baseline.v1",
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
    return run_reliability_benchmark(
        corpus,
        AdapterRegistry([MarkerAdapter()]),
    ).to_dict()


def _rebind(payload: dict[str, object]) -> None:
    payload["report_id"] = content_digest(
        {key: value for key, value in payload.items() if key != "report_id"}
    )


def _consistent_reliability_regression(payload: dict[str, object]) -> None:
    positive = payload["cases"][0]
    positive["actual_detected"] = False
    positive["confidence"] = 0.0
    payload["summary"] = {
        "true_positive": 0,
        "true_negative": 1,
        "false_positive": 0,
        "false_negative": 1,
        "accuracy": 0.5,
        "precision": None,
        "recall": 0.0,
        "specificity": 1.0,
        "false_positive_rate": 0.0,
        "false_negative_rate": 1.0,
    }
    _rebind(payload)


def test_same_verified_report_is_same_or_better(tmp_path: Path) -> None:
    payload = _report(tmp_path)
    baseline = create_benchmark_baseline(payload)

    comparison = compare_benchmark_to_baseline(payload, baseline)

    assert comparison.status is BenchmarkComparisonStatus.SAME_OR_BETTER
    assert comparison.changes == ()


def test_consistent_worse_reliability_report_is_regression(tmp_path: Path) -> None:
    baseline_report = _report(tmp_path)
    baseline = create_benchmark_baseline(baseline_report)
    current = json.loads(json.dumps(baseline_report))
    _consistent_reliability_regression(current)

    comparison = compare_benchmark_to_baseline(current, baseline)

    assert comparison.status is BenchmarkComparisonStatus.REGRESSION
    assert any("accuracy regressed" in item for item in comparison.changes)
    assert any("false_negative_rate regressed" in item for item in comparison.changes)


def test_detector_runtime_change_is_indeterminate(tmp_path: Path) -> None:
    baseline_report = _report(tmp_path)
    baseline = create_benchmark_baseline(baseline_report)
    current = json.loads(json.dumps(baseline_report))
    current["adapter_runtime"].append("adapter-runtime=model=checkpoint-2")
    _rebind(current)

    comparison = compare_benchmark_to_baseline(current, baseline)

    assert comparison.status is BenchmarkComparisonStatus.INDETERMINATE
    assert comparison.reason == "detector runtime identity changed"


def test_corpus_digest_change_is_indeterminate(tmp_path: Path) -> None:
    baseline_report = _report(tmp_path)
    baseline = create_benchmark_baseline(baseline_report)
    current = json.loads(json.dumps(baseline_report))
    current["corpus_digest"] = "a" * 64
    _rebind(current)

    comparison = compare_benchmark_to_baseline(current, baseline)

    assert comparison.status is BenchmarkComparisonStatus.INDETERMINATE
    assert comparison.reason == "benchmark corpus/matrix digest changed"


def test_baseline_is_content_addressed_and_round_trips(tmp_path: Path) -> None:
    baseline = create_benchmark_baseline(_report(tmp_path))

    loaded = baseline_from_dict(baseline.to_dict())

    assert loaded.baseline_id == baseline.baseline_id
    assert len(loaded.baseline_id) == 64


def test_rehashed_malformed_baseline_metrics_are_rejected(tmp_path: Path) -> None:
    report = _report(tmp_path)
    core = {
        "schema_version": "0.1",
        "benchmark_type": "reliability",
        "source_report_id": report["report_id"],
        "input_digest": report["corpus_digest"],
        "runtime_digest": content_digest(report["adapter_runtime"]),
        "metrics": {"accuracy": 2.0},
    }
    payload = {"baseline_id": content_digest(core), **core}

    try:
        baseline_from_dict(payload)
    except BenchmarkBaselineError as exc:
        assert "metrics are malformed" in str(exc)
    else:
        raise AssertionError("expected malformed baseline metrics to fail")


def test_baseline_cli_create_compare_and_verify_comparison(
    tmp_path: Path,
    capsys,
) -> None:
    report = _report(tmp_path)
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    baseline_path = tmp_path / "baseline.json"
    comparison_path = tmp_path / "comparison.json"

    assert (
        baseline_cli_main(
            ["create", str(report_path), "--output", str(baseline_path)]
        )
        == 0
    )
    capsys.readouterr()
    assert baseline_path.is_file()

    assert (
        baseline_cli_main(
            [
                "compare",
                str(report_path),
                "--baseline",
                str(baseline_path),
                "--output",
                str(comparison_path),
            ]
        )
        == 0
    )
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    assert comparison["status"] == "same_or_better"
    assert len(comparison["comparison_id"]) == 64

    assert (
        baseline_cli_main(["verify-comparison", str(comparison_path)])
        == 0
    )
    verification = json.loads(capsys.readouterr().out)
    assert verification["valid"] is True
