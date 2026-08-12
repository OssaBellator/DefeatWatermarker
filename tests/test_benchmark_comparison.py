from __future__ import annotations

from defeat_watermarker.benchmark_baseline import (
    BenchmarkComparison,
    BenchmarkComparisonStatus,
)
from defeat_watermarker.benchmark_comparison import (
    BenchmarkComparisonEvidence,
    from_comparison,
    verify_comparison_document,
)

BASELINE_ID = "a" * 64
REPORT_ID = "b" * 64


def test_same_or_better_comparison_is_content_addressed() -> None:
    evidence = from_comparison(
        BenchmarkComparison(
            status=BenchmarkComparisonStatus.SAME_OR_BETTER,
            baseline_id=BASELINE_ID,
            report_id=REPORT_ID,
            changes=(),
            reason="no comparable benchmark metric regressed",
        )
    )

    payload = evidence.to_dict()
    result = verify_comparison_document(payload)

    assert result.valid is True
    assert result.comparison_id == evidence.comparison_id
    assert len(evidence.comparison_id) == 64
    assert "status_semantics" in result.checks


def test_regression_requires_at_least_one_change() -> None:
    try:
        BenchmarkComparisonEvidence(
            status=BenchmarkComparisonStatus.REGRESSION,
            baseline_id=BASELINE_ID,
            report_id=REPORT_ID,
            changes=(),
            reason="regression",
        )
    except ValueError as exc:
        assert "must contain at least one change" in str(exc)
    else:
        raise AssertionError("expected regression without changes to fail")


def test_indeterminate_rejects_regression_changes() -> None:
    try:
        BenchmarkComparisonEvidence(
            status=BenchmarkComparisonStatus.INDETERMINATE,
            baseline_id=BASELINE_ID,
            report_id=REPORT_ID,
            changes=("accuracy regressed",),
            reason="detector runtime identity changed",
        )
    except ValueError as exc:
        assert "must not contain regression changes" in str(exc)
    else:
        raise AssertionError("expected indeterminate changes to fail")


def test_modified_comparison_is_rejected() -> None:
    evidence = BenchmarkComparisonEvidence(
        status=BenchmarkComparisonStatus.REGRESSION,
        baseline_id=BASELINE_ID,
        report_id=REPORT_ID,
        changes=("accuracy regressed (1.000000 -> 0.500000)",),
        reason="comparable benchmark metrics regressed",
    )
    payload = evidence.to_dict()
    payload["reason"] = "changed after generation"

    result = verify_comparison_document(payload)

    assert result.valid is False
    assert any("comparison_id does not match" in error for error in result.errors)


def test_same_or_better_with_injected_change_is_rejected_even_if_hash_is_rebound() -> None:
    evidence = BenchmarkComparisonEvidence(
        status=BenchmarkComparisonStatus.SAME_OR_BETTER,
        baseline_id=BASELINE_ID,
        report_id=REPORT_ID,
        changes=(),
        reason="no comparable benchmark metric regressed",
    )
    payload = evidence.to_dict()
    payload["changes"] = ["hidden regression"]
    from defeat_watermarker.digests import content_digest

    payload["comparison_id"] = content_digest(
        {key: value for key, value in payload.items() if key != "comparison_id"}
    )

    result = verify_comparison_document(payload)

    assert result.valid is False
    assert any("same_or_better comparison cannot contain changes" in error for error in result.errors)
