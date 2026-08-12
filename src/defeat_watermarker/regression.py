from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from .digests import content_digest
from .evidence import verify_evidence_document

_MAX_BASELINE_BYTES = 1024 * 1024
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_RATE_KEYS = (
    "survival_rate",
    "verification_survival_rate",
    "trust_survival_rate",
    "provenance_id_preservation_rate",
)


class RegressionError(ValueError):
    """Raised when a regression baseline or evidence comparison is invalid."""


@dataclass(frozen=True, slots=True)
class RegressionMetric:
    baseline: float
    max_drop: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.baseline <= 1.0:
            raise RegressionError("baseline metric must be between 0 and 1")
        if not 0.0 <= self.max_drop <= 1.0:
            raise RegressionError("max_drop must be between 0 and 1")

    def to_dict(self) -> dict[str, float]:
        return {"baseline": self.baseline, "max_drop": self.max_drop}


@dataclass(frozen=True, slots=True)
class RegressionBaseline:
    schema_version: str
    baseline_id: str
    version: str
    source_evidence_id: str
    suite_digest: str
    adapter_runtime_digest: str
    metrics: tuple[tuple[str, RegressionMetric], ...]

    def __post_init__(self) -> None:
        if self.schema_version != "0.1":
            raise RegressionError("unsupported regression baseline schema_version")
        if not _ID_RE.fullmatch(self.baseline_id):
            raise RegressionError("baseline_id must be a stable identifier")
        if not self.version or len(self.version) > 64:
            raise RegressionError("baseline version must be non-empty and at most 64 characters")
        for noun, digest in (
            ("source_evidence_id", self.source_evidence_id),
            ("suite_digest", self.suite_digest),
            ("adapter_runtime_digest", self.adapter_runtime_digest),
        ):
            if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
                raise RegressionError(f"{noun} must be a lowercase SHA-256 digest")
        if not self.metrics:
            raise RegressionError("baseline must contain at least one comparable metric")
        keys = [key for key, _ in self.metrics]
        if len(keys) != len(set(keys)):
            raise RegressionError("baseline metric keys must be unique")
        unknown = sorted(set(keys) - set(_RATE_KEYS))
        if unknown:
            raise RegressionError(f"unknown regression metrics: {', '.join(unknown)}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "baseline_id": self.baseline_id,
            "version": self.version,
            "source_evidence_id": self.source_evidence_id,
            "suite_digest": self.suite_digest,
            "adapter_runtime_digest": self.adapter_runtime_digest,
            "metrics": {key: metric.to_dict() for key, metric in self.metrics},
        }

    @property
    def digest(self) -> str:
        return content_digest(self.to_dict())


class RegressionStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True, slots=True)
class RegressionMetricResult:
    metric: str
    baseline: float
    current: float | None
    max_drop: float
    observed_drop: float | None
    passed: bool | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "baseline": self.baseline,
            "current": self.current,
            "max_drop": self.max_drop,
            "observed_drop": self.observed_drop,
            "passed": self.passed,
        }


@dataclass(frozen=True, slots=True)
class RegressionReport:
    baseline_id: str
    baseline_version: str
    baseline_digest: str
    current_evidence_id: str
    suite_match: bool
    adapter_runtime_match: bool
    metrics: tuple[RegressionMetricResult, ...]
    status: RegressionStatus
    reasons: tuple[str, ...]
    schema_version: str = "0.1"

    def core_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "baseline_id": self.baseline_id,
            "baseline_version": self.baseline_version,
            "baseline_digest": self.baseline_digest,
            "current_evidence_id": self.current_evidence_id,
            "suite_match": self.suite_match,
            "adapter_runtime_match": self.adapter_runtime_match,
            "metrics": [metric.to_dict() for metric in self.metrics],
            "status": self.status.value,
            "reasons": list(self.reasons),
        }

    @property
    def report_id(self) -> str:
        return content_digest(self.core_dict())

    def to_dict(self) -> dict[str, Any]:
        return {"report_id": self.report_id, **self.core_dict()}


def _require_valid_evidence(payload: dict[str, Any]) -> None:
    verification = verify_evidence_document(payload)
    if not verification.valid:
        raise RegressionError(
            "evidence failed self-consistency verification: " + "; ".join(verification.errors)
        )


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        raise RegressionError("evidence summary must be an object")
    return summary


def _runtime_digest(payload: dict[str, Any]) -> str:
    report = payload.get("report")
    if not isinstance(report, dict):
        raise RegressionError("evidence report must be an object")
    runtime = report.get("adapter_runtime")
    if not isinstance(runtime, dict):
        raise RegressionError("evidence report is missing adapter_runtime")
    return content_digest(runtime)


def create_regression_baseline(
    evidence: dict[str, Any],
    *,
    baseline_id: str,
    version: str,
    max_drop: float,
) -> RegressionBaseline:
    _require_valid_evidence(evidence)
    if not 0.0 <= max_drop <= 1.0:
        raise RegressionError("max_drop must be between 0 and 1")
    summary = _summary(evidence)
    metrics: list[tuple[str, RegressionMetric]] = []
    for key in _RATE_KEYS:
        value = summary.get(key)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RegressionError(f"summary metric {key} must be numeric or null")
        metrics.append((key, RegressionMetric(float(value), max_drop)))
    if not metrics:
        raise RegressionError("evidence has no comparable survival-rate metrics")
    suite = evidence.get("suite")
    if not isinstance(suite, dict) or not isinstance(suite.get("digest"), str):
        raise RegressionError("evidence suite reference is malformed")
    evidence_id = evidence.get("evidence_id")
    if not isinstance(evidence_id, str):
        raise RegressionError("evidence_id is missing")
    return RegressionBaseline(
        schema_version="0.1",
        baseline_id=baseline_id,
        version=version,
        source_evidence_id=evidence_id,
        suite_digest=suite["digest"],
        adapter_runtime_digest=_runtime_digest(evidence),
        metrics=tuple(metrics),
    )


def baseline_from_dict(payload: dict[str, Any]) -> RegressionBaseline:
    allowed = {
        "schema_version",
        "baseline_id",
        "version",
        "source_evidence_id",
        "suite_digest",
        "adapter_runtime_digest",
        "metrics",
    }
    if set(payload) != allowed:
        extras = sorted(set(payload) - allowed)
        missing = sorted(allowed - set(payload))
        if extras:
            raise RegressionError(f"baseline has unknown fields: {', '.join(extras)}")
        raise RegressionError(f"baseline is missing fields: {', '.join(missing)}")
    raw_metrics = payload["metrics"]
    if not isinstance(raw_metrics, dict):
        raise RegressionError("baseline metrics must be an object")
    metrics: list[tuple[str, RegressionMetric]] = []
    for key, raw in raw_metrics.items():
        if not isinstance(key, str) or not isinstance(raw, dict):
            raise RegressionError("baseline metric entries are malformed")
        if set(raw) != {"baseline", "max_drop"}:
            raise RegressionError(f"baseline metric {key} has invalid fields")
        baseline = raw["baseline"]
        max_drop = raw["max_drop"]
        if (
            isinstance(baseline, bool)
            or isinstance(max_drop, bool)
            or not isinstance(baseline, (int, float))
            or not isinstance(max_drop, (int, float))
        ):
            raise RegressionError(f"baseline metric {key} values must be numeric")
        metrics.append((key, RegressionMetric(float(baseline), float(max_drop))))
    return RegressionBaseline(
        schema_version=str(payload["schema_version"]),
        baseline_id=str(payload["baseline_id"]),
        version=str(payload["version"]),
        source_evidence_id=str(payload["source_evidence_id"]),
        suite_digest=str(payload["suite_digest"]),
        adapter_runtime_digest=str(payload["adapter_runtime_digest"]),
        metrics=tuple(metrics),
    )


def load_regression_baseline(path: Path) -> RegressionBaseline:
    if path.stat().st_size > _MAX_BASELINE_BYTES:
        raise RegressionError(f"baseline file exceeds {_MAX_BASELINE_BYTES} bytes")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RegressionError(f"could not read regression baseline: {exc}") from exc
    if not isinstance(payload, dict):
        raise RegressionError("regression baseline must be a JSON object")
    return baseline_from_dict(payload)


def compare_regression(
    baseline: RegressionBaseline,
    evidence: dict[str, Any],
) -> RegressionReport:
    _require_valid_evidence(evidence)
    suite = evidence.get("suite")
    if not isinstance(suite, dict):
        raise RegressionError("evidence suite reference is malformed")
    suite_match = suite.get("digest") == baseline.suite_digest
    runtime_match = _runtime_digest(evidence) == baseline.adapter_runtime_digest
    summary = _summary(evidence)
    results: list[RegressionMetricResult] = []
    missing_metrics: list[str] = []
    failed_metrics: list[str] = []

    for key, metric in baseline.metrics:
        raw = summary.get(key)
        if raw is None:
            current = None
            drop = None
            passed = None
            missing_metrics.append(key)
        elif isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise RegressionError(f"summary metric {key} must be numeric or null")
        else:
            current = float(raw)
            if not 0.0 <= current <= 1.0:
                raise RegressionError(f"summary metric {key} must be between 0 and 1")
            drop = metric.baseline - current
            passed = drop <= metric.max_drop
            if not passed:
                failed_metrics.append(key)
        results.append(
            RegressionMetricResult(
                metric=key,
                baseline=metric.baseline,
                current=current,
                max_drop=metric.max_drop,
                observed_drop=drop,
                passed=passed,
            )
        )

    reasons: list[str] = []
    if not suite_match:
        reasons.append("suite digest differs from the baseline")
    if not runtime_match:
        reasons.append("adapter runtime digest differs from the baseline")
    if missing_metrics:
        reasons.append("current evidence lacks metrics: " + ", ".join(missing_metrics))

    if reasons:
        status = RegressionStatus.INDETERMINATE
    elif failed_metrics:
        status = RegressionStatus.FAIL
        reasons.append("metrics exceeded maximum drop: " + ", ".join(failed_metrics))
    else:
        status = RegressionStatus.PASS
        reasons.append("all comparable metrics remained within configured maximum drop")

    evidence_id = evidence.get("evidence_id")
    if not isinstance(evidence_id, str):
        raise RegressionError("evidence_id is missing")
    return RegressionReport(
        baseline_id=baseline.baseline_id,
        baseline_version=baseline.version,
        baseline_digest=baseline.digest,
        current_evidence_id=evidence_id,
        suite_match=suite_match,
        adapter_runtime_match=runtime_match,
        metrics=tuple(results),
        status=status,
        reasons=tuple(reasons),
    )
