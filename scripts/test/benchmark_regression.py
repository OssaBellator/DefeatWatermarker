#!/usr/bin/env python3
from __future__ import annotations

import copy

from defeat_watermarker.benchmark_baseline import (
    BenchmarkBaselineError,
    baseline_from_dict,
    compare_benchmark_to_baseline,
    create_benchmark_baseline,
)
from defeat_watermarker.benchmark_comparison import (
    from_comparison,
    verify_comparison_document,
)
from defeat_watermarker.benchmark_evidence import verify_benchmark_document
from defeat_watermarker.digests import content_digest


def bind(core):
    return {"report_id": content_digest(core), **core}


def rebind(payload):
    payload["report_id"] = content_digest(
        {key: value for key, value in payload.items() if key != "report_id"}
    )


def reliability():
    return bind(
        {
            "schema_version": "0.2",
            "corpus_id": "local-smoke",
            "corpus_version": "0.1",
            "corpus_digest": "a" * 64,
            "adapter_id": "fixture.local.v1",
            "adapter_runtime": [
                "adapter_id=fixture.local.v1",
                "model=fixture-v1",
            ],
            "cases": [
                {
                    "case_id": "positive",
                    "artifact_sha256": "b" * 64,
                    "byte_length": 10,
                    "expected_detected": True,
                    "actual_detected": True,
                    "confidence": 1.0,
                    "verification_state": "not_evaluated",
                },
                {
                    "case_id": "negative",
                    "artifact_sha256": "c" * 64,
                    "byte_length": 9,
                    "expected_detected": False,
                    "actual_detected": False,
                    "confidence": 0.0,
                    "verification_state": "not_evaluated",
                },
            ],
            "summary": {
                "true_positive": 1,
                "true_negative": 1,
                "false_positive": 0,
                "false_negative": 0,
                "accuracy": 1.0,
                "precision": 1.0,
                "recall": 1.0,
                "specificity": 1.0,
                "false_positive_rate": 0.0,
                "false_negative_rate": 0.0,
            },
        }
    )


def interoperability():
    return bind(
        {
            "schema_version": "0.2",
            "matrix_id": "local-smoke",
            "matrix_version": "0.1",
            "matrix_digest": "d" * 64,
            "adapter_runtime": {
                "left": ["adapter_id=left"],
                "right": ["adapter_id=right"],
            },
            "cases": [
                {
                    "case_id": "one",
                    "artifact_sha256": "e" * 64,
                    "byte_length": 5,
                    "observations": [
                        {
                            "adapter_id": "left",
                            "supported": True,
                            "family": "unknown",
                            "detected": True,
                            "confidence": 1.0,
                            "verification_state": "not_evaluated",
                            "provenance_identifier": None,
                        },
                        {
                            "adapter_id": "right",
                            "supported": True,
                            "family": "unknown",
                            "detected": False,
                            "confidence": 0.0,
                            "verification_state": "not_evaluated",
                            "provenance_identifier": None,
                        },
                    ],
                }
            ],
            "pairs": [
                {
                    "left_adapter_id": "left",
                    "right_adapter_id": "right",
                    "comparable_cases": 1,
                    "detection_agreements": 0,
                    "detection_disagreements": 1,
                    "agreement_rate": 0.0,
                    "both_detected": 0,
                    "both_not_detected": 0,
                }
            ],
        }
    )


def main():
    reliability_payload = reliability()
    reliability_result = verify_benchmark_document(reliability_payload)
    assert reliability_result.valid
    assert "summary_semantics" in reliability_result.checks

    tampered = copy.deepcopy(reliability_payload)
    tampered["summary"].update(
        true_positive=0,
        false_negative=1,
        accuracy=0.5,
        recall=0.0,
        false_negative_rate=1.0,
    )
    rebind(tampered)
    assert not verify_benchmark_document(tampered).valid

    interoperability_payload = interoperability()
    interoperability_result = verify_benchmark_document(interoperability_payload)
    assert interoperability_result.valid
    assert "pair_semantics" in interoperability_result.checks

    tampered_interop = copy.deepcopy(interoperability_payload)
    tampered_interop["pairs"][0].update(
        detection_agreements=1,
        detection_disagreements=0,
        agreement_rate=1.0,
    )
    rebind(tampered_interop)
    assert not verify_benchmark_document(tampered_interop).valid

    baseline = create_benchmark_baseline(reliability_payload)
    comparison = compare_benchmark_to_baseline(reliability_payload, baseline)
    comparison_evidence = from_comparison(comparison)
    assert verify_comparison_document(comparison_evidence.to_dict()).valid

    malformed_core = {
        "schema_version": "0.1",
        "benchmark_type": "reliability",
        "source_report_id": reliability_payload["report_id"],
        "input_digest": reliability_payload["corpus_digest"],
        "runtime_digest": content_digest(reliability_payload["adapter_runtime"]),
        "metrics": {"accuracy": 2.0},
    }
    malformed = {"baseline_id": content_digest(malformed_core), **malformed_core}
    try:
        baseline_from_dict(malformed)
    except BenchmarkBaselineError:
        pass
    else:
        raise AssertionError("malformed rehashed baseline metrics accepted")

    print(
        "OK: semantic benchmark verification and baseline/comparison regression smoke"
    )


if __name__ == "__main__":
    main()
