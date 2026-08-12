from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .benchmark_evidence import verify_benchmark_document
from .digests import content_digest

_RATE_TOLERANCE = 1e-12


class BenchmarkBaselineError(ValueError):
    """Raised when a benchmark baseline is malformed or incompatible."""


class BenchmarkComparisonStatus(str, Enum):
    SAME_OR_BETTER = "same_or_better"
    REGRESSION = "regression"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True, slots=True)
class BenchmarkBaseline:
    benchmark_type: str
    source_report_id: str
    input_digest: str
    runtime_digest: str
    metrics: dict[str, Any]
    schema_version: str = "0.1"

    def core_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "benchmark_type": self.benchmark_type,
            "source_report_id": self.source_report_id,
            "input_digest": self.input_digest,
            "runtime_digest": self.runtime_digest,
            "metrics": self.metrics,
        }

    @property
    def baseline_id(self) -> str:
        return content_digest(self.core_dict())

    def to_dict(self) -> dict[str, Any]:
        return {"baseline_id": self.baseline_id, **self.core_dict()}


@dataclass(frozen=True, slots=True)
class BenchmarkComparison:
    status: BenchmarkComparisonStatus
    baseline_id: str
    report_id: str
    changes: tuple[str, ...]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "baseline_id": self.baseline_id,
            "report_id": self.report_id,
            "changes": list(self.changes),
            "reason": self.reason,
        }


def _runtime_digest(payload: dict[str, Any]) -> str:
    return content_digest(payload["adapter_runtime"])


def _input_digest(payload: dict[str, Any], benchmark_type: str) -> str:
    return str(
        payload["corpus_digest"]
        if benchmark_type == "reliability"
        else payload["matrix_digest"]
    )


def _pair_key(left: str, right: str) -> str:
    a, b = sorted((left, right))
    return f"{a}|{b}"


def _metrics(payload: dict[str, Any], benchmark_type: str) -> dict[str, Any]:
    if benchmark_type == "reliability":
        summary = payload["summary"]
        return {
            "accuracy": summary["accuracy"],
            "precision": summary["precision"],
            "recall": summary["recall"],
            "specificity": summary["specificity"],
            "false_positive_rate": summary["false_positive_rate"],
            "false_negative_rate": summary["false_negative_rate"],
            "case_count": len(payload["cases"]),
        }
    pairs: dict[str, Any] = {}
    for pair in payload["pairs"]:
        pairs[_pair_key(pair["left_adapter_id"], pair["right_adapter_id"])] = {
            "comparable_cases": pair["comparable_cases"],
            "agreement_rate": pair["agreement_rate"],
        }
    return {"case_count": len(payload["cases"]), "pairs": pairs}


def create_benchmark_baseline(payload: dict[str, Any]) -> BenchmarkBaseline:
    verification = verify_benchmark_document(payload)
    if (
        not verification.valid
        or verification.report_id is None
        or verification.benchmark_type is None
    ):
        raise BenchmarkBaselineError(
            "benchmark report must verify before it can become a baseline"
        )
    return BenchmarkBaseline(
        benchmark_type=verification.benchmark_type,
        source_report_id=verification.report_id,
        input_digest=_input_digest(payload, verification.benchmark_type),
        runtime_digest=_runtime_digest(payload),
        metrics=_metrics(payload, verification.benchmark_type),
    )


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _rate_or_none(value: Any) -> bool:
    return value is None or (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and 0.0 <= float(value) <= 1.0
    )


def _validate_metrics(benchmark_type: str, metrics: Any) -> None:
    if not isinstance(metrics, dict):
        raise BenchmarkBaselineError("benchmark baseline metrics must be an object")
    if benchmark_type == "reliability":
        expected = {
            "accuracy",
            "precision",
            "recall",
            "specificity",
            "false_positive_rate",
            "false_negative_rate",
            "case_count",
        }
        if (
            set(metrics) != expected
            or type(metrics["case_count"]) is not int
            or metrics["case_count"] < 1
        ):
            raise BenchmarkBaselineError("reliability baseline metrics are malformed")
        if any(
            not _rate_or_none(metrics[name])
            for name in expected - {"case_count"}
        ):
            raise BenchmarkBaselineError("reliability baseline rates are malformed")
        return

    if (
        set(metrics) != {"case_count", "pairs"}
        or type(metrics["case_count"]) is not int
        or metrics["case_count"] < 1
    ):
        raise BenchmarkBaselineError("interoperability baseline metrics are malformed")
    pairs = metrics["pairs"]
    if not isinstance(pairs, dict) or not pairs:
        raise BenchmarkBaselineError("interoperability baseline pairs are malformed")
    for pair_id, pair in pairs.items():
        if (
            not isinstance(pair_id, str)
            or not pair_id
            or not isinstance(pair, dict)
            or set(pair) != {"comparable_cases", "agreement_rate"}
        ):
            raise BenchmarkBaselineError(
                "interoperability baseline pair metrics are malformed"
            )
        if (
            type(pair["comparable_cases"]) is not int
            or pair["comparable_cases"] < 0
            or not _rate_or_none(pair["agreement_rate"])
        ):
            raise BenchmarkBaselineError(
                "interoperability baseline pair values are malformed"
            )


def baseline_from_dict(payload: dict[str, Any]) -> BenchmarkBaseline:
    required = {
        "baseline_id",
        "schema_version",
        "benchmark_type",
        "source_report_id",
        "input_digest",
        "runtime_digest",
        "metrics",
    }
    if set(payload) != required:
        raise BenchmarkBaselineError("benchmark baseline has invalid fields")
    if payload.get("schema_version") != "0.1":
        raise BenchmarkBaselineError("unsupported benchmark baseline schema_version")
    benchmark_type = payload.get("benchmark_type")
    if benchmark_type not in {"reliability", "interoperability"}:
        raise BenchmarkBaselineError("benchmark baseline has invalid benchmark_type")
    for field in (
        "baseline_id",
        "source_report_id",
        "input_digest",
        "runtime_digest",
    ):
        if not _is_sha256(payload.get(field)):
            raise BenchmarkBaselineError(f"benchmark baseline has invalid {field}")
    _validate_metrics(benchmark_type, payload.get("metrics"))
    baseline = BenchmarkBaseline(
        benchmark_type=benchmark_type,
        source_report_id=payload["source_report_id"],
        input_digest=payload["input_digest"],
        runtime_digest=payload["runtime_digest"],
        metrics=payload["metrics"],
        schema_version="0.1",
    )
    if baseline.baseline_id != payload["baseline_id"]:
        raise BenchmarkBaselineError(
            "baseline_id does not match benchmark baseline core"
        )
    return baseline


def _rate_change(
    name: str,
    baseline_value: Any,
    current_value: Any,
    *,
    higher_is_better: bool,
) -> str | None:
    if baseline_value is None and current_value is None:
        return None
    if baseline_value is None or current_value is None:
        return (
            f"{name} comparability changed "
            f"({baseline_value!r} -> {current_value!r})"
        )
    baseline_rate = float(baseline_value)
    current_rate = float(current_value)
    if higher_is_better:
        if current_rate + _RATE_TOLERANCE < baseline_rate:
            return (
                f"{name} regressed "
                f"({baseline_rate:.6f} -> {current_rate:.6f})"
            )
    elif current_rate > baseline_rate + _RATE_TOLERANCE:
        return (
            f"{name} regressed "
            f"({baseline_rate:.6f} -> {current_rate:.6f})"
        )
    return None


def _compare_reliability(
    baseline_metrics: dict[str, Any],
    current_metrics: dict[str, Any],
) -> tuple[str, ...]:
    changes: list[str] = []
    if baseline_metrics.get("case_count") != current_metrics.get("case_count"):
        changes.append("reliability case count changed")
    for name in ("accuracy", "precision", "recall", "specificity"):
        change = _rate_change(
            name,
            baseline_metrics.get(name),
            current_metrics.get(name),
            higher_is_better=True,
        )
        if change is not None:
            changes.append(change)
    for name in ("false_positive_rate", "false_negative_rate"):
        change = _rate_change(
            name,
            baseline_metrics.get(name),
            current_metrics.get(name),
            higher_is_better=False,
        )
        if change is not None:
            changes.append(change)
    return tuple(changes)


def _compare_interoperability(
    baseline_metrics: dict[str, Any],
    current_metrics: dict[str, Any],
) -> tuple[str, ...]:
    changes: list[str] = []
    if baseline_metrics.get("case_count") != current_metrics.get("case_count"):
        changes.append("interoperability case count changed")
    baseline_pairs = baseline_metrics.get("pairs")
    current_pairs = current_metrics.get("pairs")
    if not isinstance(baseline_pairs, dict) or not isinstance(current_pairs, dict):
        return ("interoperability pair metrics are malformed",)
    if set(baseline_pairs) != set(current_pairs):
        return ("interoperability pair set changed",)
    for pair_id in sorted(baseline_pairs):
        before = baseline_pairs[pair_id]
        after = current_pairs[pair_id]
        if before.get("comparable_cases") != after.get("comparable_cases"):
            changes.append(f"{pair_id} comparable case count changed")
            continue
        change = _rate_change(
            f"{pair_id} agreement_rate",
            before.get("agreement_rate"),
            after.get("agreement_rate"),
            higher_is_better=True,
        )
        if change is not None:
            changes.append(change)
    return tuple(changes)


def compare_benchmark_to_baseline(
    report_payload: dict[str, Any],
    baseline: BenchmarkBaseline,
) -> BenchmarkComparison:
    verification = verify_benchmark_document(report_payload)
    if (
        not verification.valid
        or verification.report_id is None
        or verification.benchmark_type is None
    ):
        raise BenchmarkBaselineError(
            "benchmark report must verify before baseline comparison"
        )
    if verification.benchmark_type != baseline.benchmark_type:
        return BenchmarkComparison(
            BenchmarkComparisonStatus.INDETERMINATE,
            baseline.baseline_id,
            verification.report_id,
            (),
            "benchmark type changed",
        )
    if (
        _input_digest(report_payload, verification.benchmark_type)
        != baseline.input_digest
    ):
        return BenchmarkComparison(
            BenchmarkComparisonStatus.INDETERMINATE,
            baseline.baseline_id,
            verification.report_id,
            (),
            "benchmark corpus/matrix digest changed",
        )
    if _runtime_digest(report_payload) != baseline.runtime_digest:
        return BenchmarkComparison(
            BenchmarkComparisonStatus.INDETERMINATE,
            baseline.baseline_id,
            verification.report_id,
            (),
            "detector runtime identity changed",
        )

    current_metrics = _metrics(report_payload, verification.benchmark_type)
    changes = (
        _compare_reliability(baseline.metrics, current_metrics)
        if verification.benchmark_type == "reliability"
        else _compare_interoperability(baseline.metrics, current_metrics)
    )
    if changes:
        return BenchmarkComparison(
            BenchmarkComparisonStatus.REGRESSION,
            baseline.baseline_id,
            verification.report_id,
            changes,
            "comparable benchmark metrics regressed",
        )
    return BenchmarkComparison(
        BenchmarkComparisonStatus.SAME_OR_BETTER,
        baseline.baseline_id,
        verification.report_id,
        (),
        "no comparable benchmark metric regressed",
    )
