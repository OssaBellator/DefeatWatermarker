from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .models import EvaluationReport, VerificationState


@dataclass(frozen=True, slots=True)
class AdapterMetrics:
    adapter_id: str
    baseline_detected: bool
    evaluated_comparisons: int
    survived: int
    survival_rate: float | None
    mean_confidence_delta: float | None
    verified_comparisons: int
    verification_survived: int
    verification_survival_rate: float | None
    trusted_comparisons: int
    trust_survived: int
    trust_survival_rate: float | None
    provenance_id_comparisons: int
    provenance_id_preserved: int
    provenance_id_preservation_rate: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "baseline_detected": self.baseline_detected,
            "evaluated_comparisons": self.evaluated_comparisons,
            "survived": self.survived,
            "survival_rate": self.survival_rate,
            "mean_confidence_delta": self.mean_confidence_delta,
            "verified_comparisons": self.verified_comparisons,
            "verification_survived": self.verification_survived,
            "verification_survival_rate": self.verification_survival_rate,
            "trusted_comparisons": self.trusted_comparisons,
            "trust_survived": self.trust_survived,
            "trust_survival_rate": self.trust_survival_rate,
            "provenance_id_comparisons": self.provenance_id_comparisons,
            "provenance_id_preserved": self.provenance_id_preserved,
            "provenance_id_preservation_rate": self.provenance_id_preservation_rate,
        }


@dataclass(frozen=True, slots=True)
class RobustnessSummary:
    adapters: tuple[AdapterMetrics, ...]
    evaluated_comparisons: int
    survived: int
    survival_rate: float | None
    verified_comparisons: int
    verification_survived: int
    verification_survival_rate: float | None
    trusted_comparisons: int
    trust_survived: int
    trust_survival_rate: float | None
    provenance_id_comparisons: int
    provenance_id_preserved: int
    provenance_id_preservation_rate: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluated_comparisons": self.evaluated_comparisons,
            "survived": self.survived,
            "survival_rate": self.survival_rate,
            "verified_comparisons": self.verified_comparisons,
            "verification_survived": self.verification_survived,
            "verification_survival_rate": self.verification_survival_rate,
            "trusted_comparisons": self.trusted_comparisons,
            "trust_survived": self.trust_survived,
            "trust_survival_rate": self.trust_survival_rate,
            "provenance_id_comparisons": self.provenance_id_comparisons,
            "provenance_id_preserved": self.provenance_id_preserved,
            "provenance_id_preservation_rate": self.provenance_id_preservation_rate,
            "adapters": [item.to_dict() for item in self.adapters],
        }


class GateStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True, slots=True)
class GatePolicy:
    min_survival_rate: float | None = None
    min_verification_survival_rate: float | None = None
    min_trust_survival_rate: float | None = None
    min_provenance_id_preservation_rate: float | None = None
    min_evaluated_comparisons: int = 1

    def __post_init__(self) -> None:
        thresholds = (
            self.min_survival_rate,
            self.min_verification_survival_rate,
            self.min_trust_survival_rate,
            self.min_provenance_id_preservation_rate,
        )
        if all(value is None for value in thresholds):
            raise ValueError("gate policy requires at least one threshold")
        for value in thresholds:
            if value is not None and not 0.0 <= value <= 1.0:
                raise ValueError("gate thresholds must be between 0 and 1")
        if self.min_evaluated_comparisons < 1:
            raise ValueError("min_evaluated_comparisons must be positive")

    def to_dict(self) -> dict[str, Any]:
        return {
            "min_survival_rate": self.min_survival_rate,
            "min_verification_survival_rate": self.min_verification_survival_rate,
            "min_trust_survival_rate": self.min_trust_survival_rate,
            "min_provenance_id_preservation_rate": self.min_provenance_id_preservation_rate,
            "min_evaluated_comparisons": self.min_evaluated_comparisons,
        }


@dataclass(frozen=True, slots=True)
class GateResult:
    status: GateStatus
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"status": self.status.value, "reason": self.reason}


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def summarize_report(report: EvaluationReport) -> RobustnessSummary:
    baseline = {item.adapter_id: item for item in report.baseline}
    metrics: list[AdapterMetrics] = []
    totals = {
        "detection_count": 0,
        "detection_survived": 0,
        "verified_count": 0,
        "verified_survived": 0,
        "trusted_count": 0,
        "trusted_survived": 0,
        "provenance_count": 0,
        "provenance_preserved": 0,
    }

    for adapter_id in sorted(baseline):
        baseline_result = baseline[adapter_id]
        all_comparisons = [
            comparison
            for scenario in report.scenarios
            for comparison in scenario.comparisons
            if comparison.adapter_id == adapter_id
        ]
        detection = [item for item in all_comparisons if item.baseline.detected]
        verified = [
            item for item in all_comparisons if item.baseline.cryptographically_verified
        ]
        trusted = [
            item
            for item in all_comparisons
            if item.baseline.verification_state is VerificationState.TRUSTED
        ]
        provenance = [
            item
            for item in all_comparisons
            if item.baseline.provenance_identifier is not None
        ]

        survived = sum(1 for item in detection if item.survived)
        verified_survived = sum(1 for item in verified if item.verification_survived is True)
        trusted_survived = sum(1 for item in trusted if item.trust_survived is True)
        provenance_preserved = sum(
            1 for item in provenance if item.provenance_identifier_preserved is True
        )
        deltas = [item.confidence_delta for item in detection]

        metrics.append(
            AdapterMetrics(
                adapter_id=adapter_id,
                baseline_detected=baseline_result.detected,
                evaluated_comparisons=len(detection),
                survived=survived,
                survival_rate=_rate(survived, len(detection)),
                mean_confidence_delta=(sum(deltas) / len(deltas) if deltas else None),
                verified_comparisons=len(verified),
                verification_survived=verified_survived,
                verification_survival_rate=_rate(verified_survived, len(verified)),
                trusted_comparisons=len(trusted),
                trust_survived=trusted_survived,
                trust_survival_rate=_rate(trusted_survived, len(trusted)),
                provenance_id_comparisons=len(provenance),
                provenance_id_preserved=provenance_preserved,
                provenance_id_preservation_rate=_rate(
                    provenance_preserved, len(provenance)
                ),
            )
        )
        totals["detection_count"] += len(detection)
        totals["detection_survived"] += survived
        totals["verified_count"] += len(verified)
        totals["verified_survived"] += verified_survived
        totals["trusted_count"] += len(trusted)
        totals["trusted_survived"] += trusted_survived
        totals["provenance_count"] += len(provenance)
        totals["provenance_preserved"] += provenance_preserved

    return RobustnessSummary(
        adapters=tuple(metrics),
        evaluated_comparisons=totals["detection_count"],
        survived=totals["detection_survived"],
        survival_rate=_rate(totals["detection_survived"], totals["detection_count"]),
        verified_comparisons=totals["verified_count"],
        verification_survived=totals["verified_survived"],
        verification_survival_rate=_rate(
            totals["verified_survived"], totals["verified_count"]
        ),
        trusted_comparisons=totals["trusted_count"],
        trust_survived=totals["trusted_survived"],
        trust_survival_rate=_rate(totals["trusted_survived"], totals["trusted_count"]),
        provenance_id_comparisons=totals["provenance_count"],
        provenance_id_preserved=totals["provenance_preserved"],
        provenance_id_preservation_rate=_rate(
            totals["provenance_preserved"], totals["provenance_count"]
        ),
    )


def apply_gate(summary: RobustnessSummary, policy: GatePolicy) -> GateResult:
    checks = (
        (
            "detection survival",
            policy.min_survival_rate,
            summary.evaluated_comparisons,
            summary.survival_rate,
        ),
        (
            "cryptographic verification survival",
            policy.min_verification_survival_rate,
            summary.verified_comparisons,
            summary.verification_survival_rate,
        ),
        (
            "trust survival",
            policy.min_trust_survival_rate,
            summary.trusted_comparisons,
            summary.trust_survival_rate,
        ),
        (
            "provenance identifier preservation",
            policy.min_provenance_id_preservation_rate,
            summary.provenance_id_comparisons,
            summary.provenance_id_preservation_rate,
        ),
    )
    failures: list[str] = []
    indeterminate: list[str] = []
    for label, threshold, count, rate in checks:
        if threshold is None:
            continue
        if count < policy.min_evaluated_comparisons or rate is None:
            indeterminate.append(
                f"{label} has {count} eligible comparisons; "
                f"requires {policy.min_evaluated_comparisons}"
            )
            continue
        if rate < threshold:
            failures.append(f"{label} {rate:.3f} is below required {threshold:.3f}")

    if failures:
        return GateResult(GateStatus.FAIL, "; ".join(failures))
    if indeterminate:
        return GateResult(GateStatus.INDETERMINATE, "; ".join(indeterminate))
    return GateResult(GateStatus.PASS, "all requested robustness thresholds were met")
