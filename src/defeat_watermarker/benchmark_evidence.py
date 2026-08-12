from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .digests import content_digest

_MAX_BENCHMARK_BYTES = 20 * 1024 * 1024
_MAX_CASES = 1000
_MAX_RUNTIME_ITEMS = 16
_MAX_RUNTIME_ITEM_LENGTH = 512

_RELIABILITY_FIELDS = {
    "report_id",
    "schema_version",
    "corpus_id",
    "corpus_version",
    "corpus_digest",
    "adapter_id",
    "adapter_runtime",
    "cases",
    "summary",
}
_INTEROPERABILITY_FIELDS = {
    "report_id",
    "schema_version",
    "matrix_id",
    "matrix_version",
    "matrix_digest",
    "adapter_runtime",
    "cases",
    "pairs",
}


class BenchmarkEvidenceError(ValueError):
    """Raised when benchmark evidence is malformed or exceeds bounded limits."""


@dataclass(frozen=True, slots=True)
class BenchmarkVerificationResult:
    valid: bool
    benchmark_type: str | None
    report_id: str | None
    checks: tuple[str, ...]
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "benchmark_type": self.benchmark_type,
            "report_id": self.report_id,
            "checks": list(self.checks),
            "errors": list(self.errors),
        }


def _looks_like_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _runtime_list_valid(value: Any) -> bool:
    return (
        isinstance(value, list)
        and 1 <= len(value) <= _MAX_RUNTIME_ITEMS
        and all(
            isinstance(item, str) and 0 < len(item) <= _MAX_RUNTIME_ITEM_LENGTH
            for item in value
        )
    )


def _benchmark_type(payload: dict[str, Any]) -> str | None:
    keys = set(payload)
    if keys == _RELIABILITY_FIELDS:
        return "reliability"
    if keys == _INTEROPERABILITY_FIELDS:
        return "interoperability"
    if "corpus_id" in payload or "summary" in payload:
        return "reliability"
    if "matrix_id" in payload or "pairs" in payload:
        return "interoperability"
    return None


def _check_exact_fields(
    payload: dict[str, Any], expected: set[str], noun: str, errors: list[str]
) -> bool:
    keys = set(payload)
    missing = sorted(expected - keys)
    extras = sorted(keys - expected)
    if missing:
        errors.append(f"{noun} missing fields: {', '.join(missing)}")
    if extras:
        errors.append(f"{noun} has unknown fields: {', '.join(extras)}")
    return not missing and not extras


def _check_cases(cases: Any, errors: list[str], checks: list[str]) -> None:
    if not isinstance(cases, list) or not 1 <= len(cases) <= _MAX_CASES:
        errors.append(f"cases must contain 1..{_MAX_CASES} entries")
    elif any(not isinstance(case, dict) for case in cases):
        errors.append("cases must contain objects")
    else:
        checks.append("cases")


def verify_benchmark_document(payload: dict[str, Any]) -> BenchmarkVerificationResult:
    checks: list[str] = []
    errors: list[str] = []
    benchmark_type = _benchmark_type(payload)
    if benchmark_type is None:
        return BenchmarkVerificationResult(
            valid=False,
            benchmark_type=None,
            report_id=None,
            checks=(),
            errors=("document is not a recognized reliability/interoperability report",),
        )

    expected_fields = (
        _RELIABILITY_FIELDS if benchmark_type == "reliability" else _INTEROPERABILITY_FIELDS
    )
    exact_fields = _check_exact_fields(
        payload, expected_fields, f"{benchmark_type} report", errors
    )
    if exact_fields:
        checks.append("fields")

    report_id = payload.get("report_id")
    if not _looks_like_sha256(report_id):
        errors.append("report_id is not a lowercase SHA-256 digest")
    else:
        core = {key: value for key, value in payload.items() if key != "report_id"}
        if content_digest(core) != report_id:
            errors.append("report_id does not match benchmark report core")
        else:
            checks.append("report_id")

    if payload.get("schema_version") != "0.2":
        errors.append("unsupported benchmark report schema_version")
    else:
        checks.append("schema_version")

    _check_cases(payload.get("cases"), errors, checks)
    runtime = payload.get("adapter_runtime")

    if benchmark_type == "reliability":
        for field in ("corpus_id", "corpus_version", "adapter_id"):
            value = payload.get(field)
            if not isinstance(value, str) or not value:
                errors.append(f"{field} must be a non-empty string")
        if not _looks_like_sha256(payload.get("corpus_digest")):
            errors.append("corpus_digest is not a lowercase SHA-256 digest")
        else:
            checks.append("corpus_digest")

        if not _runtime_list_valid(runtime):
            errors.append("adapter_runtime must be a bounded non-empty string array")
        else:
            checks.append("adapter_runtime")

        summary = payload.get("summary")
        required_summary = {
            "true_positive",
            "true_negative",
            "false_positive",
            "false_negative",
            "accuracy",
            "precision",
            "recall",
            "specificity",
            "false_positive_rate",
            "false_negative_rate",
        }
        if not isinstance(summary, dict) or set(summary) != required_summary:
            errors.append("reliability summary has invalid fields")
        else:
            counts = (
                summary["true_positive"],
                summary["true_negative"],
                summary["false_positive"],
                summary["false_negative"],
            )
            if any(type(value) is not int or value < 0 for value in counts):
                errors.append("reliability confusion-matrix counts must be non-negative integers")
            rate_names = (
                "accuracy",
                "precision",
                "recall",
                "specificity",
                "false_positive_rate",
                "false_negative_rate",
            )
            invalid_rate = False
            for name in rate_names:
                value = summary[name]
                if value is not None and (
                    not isinstance(value, (int, float))
                    or isinstance(value, bool)
                    or not 0.0 <= float(value) <= 1.0
                ):
                    invalid_rate = True
                    break
            if invalid_rate:
                errors.append("reliability rates must be null or between 0 and 1")
            else:
                checks.append("summary")
    else:
        for field in ("matrix_id", "matrix_version"):
            value = payload.get(field)
            if not isinstance(value, str) or not value:
                errors.append(f"{field} must be a non-empty string")
        if not _looks_like_sha256(payload.get("matrix_digest")):
            errors.append("matrix_digest is not a lowercase SHA-256 digest")
        else:
            checks.append("matrix_digest")

        if not isinstance(runtime, dict) or not runtime:
            errors.append("adapter_runtime must be a non-empty object")
        elif any(
            not isinstance(adapter_id, str)
            or not adapter_id
            or not _runtime_list_valid(identity)
            for adapter_id, identity in runtime.items()
        ):
            errors.append("adapter_runtime contains invalid runtime identities")
        else:
            checks.append("adapter_runtime")

        pairs = payload.get("pairs")
        if not isinstance(pairs, list) or not pairs:
            errors.append("pairs must be a non-empty array")
        elif any(not isinstance(pair, dict) for pair in pairs):
            errors.append("pairs must contain objects")
        else:
            checks.append("pairs")

    return BenchmarkVerificationResult(
        valid=not errors,
        benchmark_type=benchmark_type,
        report_id=report_id if isinstance(report_id, str) else None,
        checks=tuple(checks),
        errors=tuple(errors),
    )


def load_benchmark_document(path: Path) -> dict[str, Any]:
    if path.stat().st_size > _MAX_BENCHMARK_BYTES:
        raise BenchmarkEvidenceError(
            f"benchmark evidence file exceeds {_MAX_BENCHMARK_BYTES} bytes"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BenchmarkEvidenceError(f"could not read benchmark evidence: {exc}") from exc
    if not isinstance(payload, dict):
        raise BenchmarkEvidenceError("benchmark evidence must be a JSON object")
    return payload
