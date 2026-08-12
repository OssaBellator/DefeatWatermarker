from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .benchmark_baseline import BenchmarkComparison, BenchmarkComparisonStatus
from .digests import content_digest

_MAX_COMPARISON_BYTES = 2 * 1024 * 1024
_MAX_CHANGES = 128
_MAX_CHANGE_LENGTH = 1024
_MAX_REASON_LENGTH = 2048


class BenchmarkComparisonError(ValueError):
    """Raised when benchmark-comparison evidence is malformed or inconsistent."""


@dataclass(frozen=True, slots=True)
class BenchmarkComparisonEvidence:
    status: BenchmarkComparisonStatus
    baseline_id: str
    report_id: str
    changes: tuple[str, ...]
    reason: str
    schema_version: str = "0.1"

    def __post_init__(self) -> None:
        for noun, value in (("baseline_id", self.baseline_id), ("report_id", self.report_id)):
            if not _is_sha256(value):
                raise BenchmarkComparisonError(f"{noun} must be a lowercase SHA-256 digest")
        if len(self.changes) > _MAX_CHANGES:
            raise BenchmarkComparisonError(f"comparison exceeds {_MAX_CHANGES} change entries")
        for item in self.changes:
            if not item or len(item) > _MAX_CHANGE_LENGTH or "\n" in item or "\r" in item:
                raise BenchmarkComparisonError("comparison contains an invalid change entry")
        if not self.reason or len(self.reason) > _MAX_REASON_LENGTH:
            raise BenchmarkComparisonError("comparison reason is missing or too long")
        if "\n" in self.reason or "\r" in self.reason:
            raise BenchmarkComparisonError("comparison reason must be a single line")
        if self.status is BenchmarkComparisonStatus.SAME_OR_BETTER and self.changes:
            raise BenchmarkComparisonError("same_or_better comparison cannot contain changes")
        if self.status is BenchmarkComparisonStatus.REGRESSION and not self.changes:
            raise BenchmarkComparisonError("regression comparison must contain at least one change")
        if self.status is BenchmarkComparisonStatus.INDETERMINATE and self.changes:
            raise BenchmarkComparisonError("indeterminate comparison must not contain regression changes")

    def core_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "status": self.status.value,
            "baseline_id": self.baseline_id,
            "report_id": self.report_id,
            "changes": list(self.changes),
            "reason": self.reason,
        }

    @property
    def comparison_id(self) -> str:
        return content_digest(self.core_dict())

    def to_dict(self) -> dict[str, Any]:
        return {"comparison_id": self.comparison_id, **self.core_dict()}


@dataclass(frozen=True, slots=True)
class BenchmarkComparisonVerification:
    valid: bool
    comparison_id: str | None
    checks: tuple[str, ...]
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "comparison_id": self.comparison_id,
            "checks": list(self.checks),
            "errors": list(self.errors),
        }


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def from_comparison(comparison: BenchmarkComparison) -> BenchmarkComparisonEvidence:
    return BenchmarkComparisonEvidence(
        status=comparison.status,
        baseline_id=comparison.baseline_id,
        report_id=comparison.report_id,
        changes=comparison.changes,
        reason=comparison.reason,
    )


def comparison_from_dict(payload: dict[str, Any]) -> BenchmarkComparisonEvidence:
    required = {
        "comparison_id",
        "schema_version",
        "status",
        "baseline_id",
        "report_id",
        "changes",
        "reason",
    }
    if set(payload) != required:
        raise BenchmarkComparisonError("benchmark comparison has invalid fields")
    if payload.get("schema_version") != "0.1":
        raise BenchmarkComparisonError("unsupported benchmark comparison schema_version")
    try:
        status = BenchmarkComparisonStatus(payload.get("status"))
    except (TypeError, ValueError) as exc:
        raise BenchmarkComparisonError("benchmark comparison has invalid status") from exc
    changes = payload.get("changes")
    if not isinstance(changes, list) or not all(isinstance(item, str) for item in changes):
        raise BenchmarkComparisonError("benchmark comparison changes must be an array of strings")
    reason = payload.get("reason")
    if not isinstance(reason, str):
        raise BenchmarkComparisonError("benchmark comparison reason must be a string")
    evidence = BenchmarkComparisonEvidence(
        status=status,
        baseline_id=payload.get("baseline_id"),
        report_id=payload.get("report_id"),
        changes=tuple(changes),
        reason=reason,
        schema_version="0.1",
    )
    if evidence.comparison_id != payload.get("comparison_id"):
        raise BenchmarkComparisonError("comparison_id does not match benchmark comparison core")
    return evidence


def verify_comparison_document(payload: dict[str, Any]) -> BenchmarkComparisonVerification:
    try:
        evidence = comparison_from_dict(payload)
    except BenchmarkComparisonError as exc:
        comparison_id = payload.get("comparison_id") if isinstance(payload, dict) else None
        return BenchmarkComparisonVerification(
            valid=False,
            comparison_id=comparison_id if isinstance(comparison_id, str) else None,
            checks=(),
            errors=(str(exc),),
        )
    return BenchmarkComparisonVerification(
        valid=True,
        comparison_id=evidence.comparison_id,
        checks=("fields", "schema_version", "status_semantics", "comparison_id"),
        errors=(),
    )


def load_comparison_document(path: Path) -> dict[str, Any]:
    if path.stat().st_size > _MAX_COMPARISON_BYTES:
        raise BenchmarkComparisonError(
            f"benchmark comparison file exceeds {_MAX_COMPARISON_BYTES} bytes"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BenchmarkComparisonError(f"could not read benchmark comparison: {exc}") from exc
    if not isinstance(payload, dict):
        raise BenchmarkComparisonError("benchmark comparison must be a JSON object")
    return payload
