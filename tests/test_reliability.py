import json

import pytest

from defeat_watermarker.adapters.metadata import ContainerHintAdapter
from defeat_watermarker.registry import AdapterRegistry
from defeat_watermarker.reliability import (
    ReliabilityError,
    corpus_from_dict,
    run_reliability_benchmark,
)


def _payload() -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "corpus_id": "fixture",
        "version": "0.1",
        "adapter_id": "builtin.container-hints.v1",
        "description": "fixture corpus",
        "cases": [
            {
                "case_id": "positive",
                "path": "positive.dat",
                "media_type": "application/octet-stream",
                "modality": "unknown",
                "expected_detected": True,
            },
            {
                "case_id": "negative",
                "path": "negative.dat",
                "media_type": "application/octet-stream",
                "modality": "unknown",
                "expected_detected": False,
            },
        ],
    }


def test_fixed_corpus_reports_false_positive_and_negative_rates(tmp_path) -> None:
    payload = _payload()
    corpus_path = tmp_path / "corpus.json"
    corpus_path.write_text(json.dumps(payload), encoding="utf-8")
    (tmp_path / "positive.dat").write_bytes(b"header c2pa footer")
    (tmp_path / "negative.dat").write_bytes(b"plain content")

    report = run_reliability_benchmark(
        corpus_path, AdapterRegistry([ContainerHintAdapter()])
    )
    assert report.summary.true_positive == 1
    assert report.summary.true_negative == 1
    assert report.summary.false_positive_rate == 0.0
    assert report.summary.false_negative_rate == 0.0
    assert report.schema_version == "0.2"
    assert any(item.startswith("adapter_id=") for item in report.adapter_runtime)
    assert any(item.startswith("python=") for item in report.adapter_runtime)
    assert len(report.report_id) == 64
    assert "header c2pa footer" not in repr(report.to_dict())


def test_corpus_rejects_path_traversal() -> None:
    payload = _payload()
    payload["cases"][0]["path"] = "../outside.dat"  # type: ignore[index]
    with pytest.raises(ReliabilityError, match="normalized relative"):
        corpus_from_dict(payload)


def test_corpus_rejects_non_boolean_labels() -> None:
    payload = _payload()
    payload["cases"][0]["expected_detected"] = 1  # type: ignore[index]
    with pytest.raises(ReliabilityError, match="must be boolean"):
        corpus_from_dict(payload)
