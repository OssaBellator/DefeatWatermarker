from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .models import EvaluationReport


@dataclass(frozen=True, slots=True)
class AdapterMetrics:
    adapter_id: str
    baseline_detected: bool
    evaluated_comparisons: int
    survived: int
    survival_rate: float | None
    mean_confidence_delta: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "baseline_detected": self.baseline_detected,
            "evaluated_comparisons": self.evaluated_comparisons,
            "survived": self.survived,
            "survival_rate": self.survival_rate,
            "mean_confidence_delta": self.mean_confidence_delta,
        }


@dataclass(frozen=True, slots=True)
class RobustnessSummary:
    adapters: tuple[AdapterMetrics, ...]
    evaluated_comparisons: int
    survived: int
    survival_rate: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluated_comparisons": self.evaluated_comparisons,
            "survived": self.survived,
            "survival_rate": self.survival_rate,
            "adapters": [item.to_dict() for item in self.adapters],
        }


class GateStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True, slots=True)
class GatePolicy:
    min_survival_rate: float = 1.0
    min_evaluated_comparisons: int = 1

    def __post_init__(self) -> None:
        if not 0.0 <= self.min_survival_rate <= 1.0:
            raise ValueError("min_survival_rate must be between 0 and 1")
        if self.min_evaluated_comparisons < 1:
            raise ValueError("min_evaluated_comparisons must be positive")


@dataclass(frozen=True, slots=True)
class GateResult:
    status: GateStatus
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"status": self.status.value, "reason": self.reason}


def summarize_report(report: EvaluationReport) -> RobustnessSummary:
    baseline = {item.adapter_id: item for item in report.baseline}
    metrics: list[AdapterMetrics] = []
    total = 0
    survived_total = 0

    for adapter_id in sorted(baseline):
        baseline_result = baseline[adapter_id]
        comparisons = [
            comparison
            for scenario in report.scenarios
            for comparison in scenario.comparisons
            if comparison.adapter_id == adapter_id and comparison.baseline.detected
        ]
        survived = sum(1 for item in comparisons if item.survived)
        deltas = [item.confidence_delta for item in comparisons]
        count = len(comparisons)
        rate = survived / count if count else None
        mean_delta = sum(deltas) / count if count else None
        metrics.append(
            AdapterMetrics(
                adapter_id=adapter_id,
                baseline_detected=baseline_result.detected,
                evaluated_comparisons=count,
                survived=survived,
                survival_rate=rate,
                mean_confidence_delta=mean_delta,
            )
        )
        total += count
        survived_total += survived

    return RobustnessSummary(
        adapters=tuple(metrics),
        evaluated_comparisons=total,
        survived=survived_total,
        survival_rate=survived_total / total if total else None,
    )


def apply_gate(summary: RobustnessSummary, policy: GatePolicy) -> GateResult:
    if summary.evaluated_comparisons < policy.min_evaluated_comparisons:
        return GateResult(
            GateStatus.INDETERMINATE,
            "not enough baseline-detected watermark/provenance comparisons were evaluated",
        )
    assert summary.survival_rate is not None
    if summary.survival_rate < policy.min_survival_rate:
        return GateResult(
            GateStatus.FAIL,
            f"survival rate {summary.survival_rate:.3f} is below required {policy.min_survival_rate:.3f}",
        )
    return GateResult(
        GateStatus.PASS,
        f"survival rate {summary.survival_rate:.3f} meets required {policy.min_survival_rate:.3f}",
    )
