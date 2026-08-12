from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .regression import RegressionBaseline, compare_regression

_MAX_REGRESSION_REPORT_BYTES = 2 * 1024 * 1024
_REPORT_FIELDS = {
    "report_id",
    "schema_version",
    "baseline_id",
    "baseline_version",
    "baseline_digest",
    "current_evidence_id",
    "suite_match",
    "adapter_runtime_match",
    "metrics",
    "status",
    "reasons",
}


class RegressionVerificationError(ValueError):
    """Raised when saved regression-report evidence is malformed or unreadable."""


@dataclass(frozen=True, slots=True)
class RegressionReportVerification:
    valid: bool
    report_id: str | None
    checks: tuple[str, ...]
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "report_id": self.report_id,
            "checks": list(self.checks),
            "errors": list(self.errors),
        }


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def load_regression_report(path: Path) -> dict[str, Any]:
    if path.stat().st_size > _MAX_REGRESSION_REPORT_BYTES:
        raise RegressionVerificationError(
            f"regression report exceeds {_MAX_REGRESSION_REPORT_BYTES} bytes"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RegressionVerificationError(
            f"could not read regression report: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise RegressionVerificationError("regression report must be a JSON object")
    return payload


def verify_regression_report(
    payload: dict[str, Any],
    baseline: RegressionBaseline,
    evidence: dict[str, Any],
) -> RegressionReportVerification:
    checks: list[str] = []
    errors: list[str] = []

    if set(payload) != _REPORT_FIELDS:
        missing = sorted(_REPORT_FIELDS - set(payload))
        extras = sorted(set(payload) - _REPORT_FIELDS)
        if missing:
            errors.append("missing fields: " + ", ".join(missing))
        if extras:
            errors.append("unknown fields: " + ", ".join(extras))
        return RegressionReportVerification(False, None, (), tuple(errors))

    report_id = payload.get("report_id")
    if not _is_sha256(report_id):
        errors.append("report_id is not a lowercase SHA-256 digest")
    else:
        checks.append("report_id_shape")

    if payload.get("schema_version") != "0.1":
        errors.append("unsupported regression report schema_version")
    else:
        checks.append("schema_version")

    try:
        expected = compare_regression(baseline, evidence).to_dict()
    except Exception as exc:
        errors.append(f"could not recompute regression comparison: {exc}")
        return RegressionReportVerification(
            valid=False,
            report_id=report_id if isinstance(report_id, str) else None,
            checks=tuple(checks),
            errors=tuple(errors),
        )

    if payload != expected:
        errors.append("regression report does not match recomputed baseline/evidence comparison")
    else:
        checks.extend(("report_id", "comparison_semantics"))

    return RegressionReportVerification(
        valid=not errors,
        report_id=report_id if isinstance(report_id, str) else None,
        checks=tuple(checks),
        errors=tuple(errors),
    )
