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
        and len(value) <= _MAX_RUNTIME_ITEMS
        and all(
            isinstance(item, str) and len(item) <= _MAX_RUNTIME_ITEM_LENGTH
            for item in value
        )
    )


def _benchmark_type(payload: dict[str, Any]) -> str | None:
    if "corpus_id" in payload and "summary" in payload and "adapter_id" in payload:
        return "reliability"
    if "matrix_id" in payload and "pairs" in payload and "adapter_runtime" in payload:
        return "interoperability"
    return None


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

    cases = payload.get("cases")
    if not isinstance(cases, list) or not 1 <= len(cases) <= _MAX_CASES:
        errors.append(f"cases must contain 1..{_MAX_CASES} entries")
    elif any(not isinstance(case, dict) for case in cases):
        errors.append("cases must contain objects")
    else:
        checks.append("cases")

    runtime = payload.get("adapter_runtime")
    if benchmark_type == "reliability":
        if not _runtime_list_valid(runtime):
            errors.append("adapter_runtime must be a bounded string array")
        else:
            checks.append("adapter_runtime")
        summary = payload.get("summary")
        if not isinstance(summary, dict):
            errors.append("summary must be an object")
        else:
            required_counts = {
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
            if set(summary) != required_counts:
                errors.append("reliability summary has invalid fields")
            else:
                checks.append("summary")
    else:
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
