from __future__ import annotations

import json
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

from .digests import content_digest

_MAX_BENCHMARK_BYTES = 20 * 1024 * 1024
_MAX_CASES = 1000
_MAX_RUNTIME_ITEMS = 16
_MAX_RUNTIME_ITEM_LENGTH = 512
_MAX_ADAPTERS = 16
_RATE_TOLERANCE = 1e-12

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
_RELIABILITY_CASE_FIELDS = {
    "case_id",
    "artifact_sha256",
    "byte_length",
    "expected_detected",
    "actual_detected",
    "confidence",
    "verification_state",
}
_INTEROPERABILITY_CASE_FIELDS = {
    "case_id",
    "artifact_sha256",
    "byte_length",
    "observations",
}
_OBSERVATION_FIELDS = {
    "adapter_id",
    "supported",
    "family",
    "detected",
    "confidence",
    "verification_state",
    "provenance_identifier",
}
_PAIR_FIELDS = {
    "left_adapter_id",
    "right_adapter_id",
    "comparable_cases",
    "detection_agreements",
    "detection_disagreements",
    "agreement_rate",
    "both_detected",
    "both_not_detected",
}
_SUMMARY_FIELDS = {
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
    value: dict[str, Any],
    expected: set[str],
    noun: str,
    errors: list[str],
) -> bool:
    missing = sorted(expected - set(value))
    extras = sorted(set(value) - expected)
    if missing:
        errors.append(f"{noun} missing fields: {', '.join(missing)}")
    if extras:
        errors.append(f"{noun} has unknown fields: {', '.join(extras)}")
    return not missing and not extras


def _is_rate(value: Any, *, nullable: bool = True) -> bool:
    if value is None:
        return nullable
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and 0.0 <= float(value) <= 1.0
    )


def _same_rate(left: float | None, right: Any) -> bool:
    if left is None or right is None:
        return left is None and right is None
    if not isinstance(right, (int, float)) or isinstance(right, bool):
        return False
    return abs(float(left) - float(right)) <= _RATE_TOLERANCE


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _validate_reliability_cases(
    cases: Any,
    errors: list[str],
) -> list[dict[str, Any]] | None:
    if not isinstance(cases, list) or not 1 <= len(cases) <= _MAX_CASES:
        errors.append(f"cases must contain 1..{_MAX_CASES} entries")
        return None
    validated: list[dict[str, Any]] = []
    case_ids: set[str] = set()
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            errors.append(f"case {index} must be an object")
            continue
        if not _check_exact_fields(
            case,
            _RELIABILITY_CASE_FIELDS,
            f"case {index}",
            errors,
        ):
            continue
        case_id = case["case_id"]
        if not isinstance(case_id, str) or not case_id or case_id in case_ids:
            errors.append(f"case {index} has invalid or duplicate case_id")
        else:
            case_ids.add(case_id)
        if not _looks_like_sha256(case["artifact_sha256"]):
            errors.append(f"case {index} artifact_sha256 is invalid")
        if type(case["byte_length"]) is not int or case["byte_length"] < 0:
            errors.append(f"case {index} byte_length must be a non-negative integer")
        if (
            type(case["expected_detected"]) is not bool
            or type(case["actual_detected"]) is not bool
        ):
            errors.append(f"case {index} detection labels must be booleans")
        if not _is_rate(case["confidence"], nullable=False):
            errors.append(f"case {index} confidence must be between 0 and 1")
        if (
            not isinstance(case["verification_state"], str)
            or not case["verification_state"]
        ):
            errors.append(f"case {index} verification_state must be a non-empty string")
        validated.append(case)
    return validated if len(validated) == len(cases) else None


def _validate_reliability_summary(
    cases: list[dict[str, Any]],
    summary: Any,
    errors: list[str],
    checks: list[str],
) -> None:
    if not isinstance(summary, dict) or set(summary) != _SUMMARY_FIELDS:
        errors.append("reliability summary has invalid fields")
        return
    counts = tuple(
        summary[name]
        for name in (
            "true_positive",
            "true_negative",
            "false_positive",
            "false_negative",
        )
    )
    if any(type(value) is not int or value < 0 for value in counts):
        errors.append("reliability confusion-matrix counts must be non-negative integers")
        return
    for name in (
        "accuracy",
        "precision",
        "recall",
        "specificity",
        "false_positive_rate",
        "false_negative_rate",
    ):
        if not _is_rate(summary[name]):
            errors.append("reliability rates must be null or between 0 and 1")
            return

    tp = sum(
        1
        for case in cases
        if case["expected_detected"] and case["actual_detected"]
    )
    tn = sum(
        1
        for case in cases
        if not case["expected_detected"] and not case["actual_detected"]
    )
    fp = sum(
        1
        for case in cases
        if not case["expected_detected"] and case["actual_detected"]
    )
    fn = sum(
        1
        for case in cases
        if case["expected_detected"] and not case["actual_detected"]
    )
    expected_counts = (tp, tn, fp, fn)
    if counts != expected_counts:
        errors.append("reliability confusion-matrix counts do not match cases")
        return

    total = len(cases)
    expected_rates = {
        "accuracy": (tp + tn) / total,
        "precision": _ratio(tp, tp + fp),
        "recall": _ratio(tp, tp + fn),
        "specificity": _ratio(tn, tn + fp),
        "false_positive_rate": _ratio(fp, fp + tn),
        "false_negative_rate": _ratio(fn, fn + tp),
    }
    mismatches = [
        name
        for name, expected in expected_rates.items()
        if not _same_rate(expected, summary[name])
    ]
    if mismatches:
        errors.append("reliability rates do not match cases: " + ", ".join(mismatches))
        return
    checks.extend(("summary", "summary_semantics"))


def _validate_interop_cases(
    cases: Any,
    runtime: dict[str, Any],
    errors: list[str],
) -> list[dict[str, Any]] | None:
    if not isinstance(cases, list) or not 1 <= len(cases) <= _MAX_CASES:
        errors.append(f"cases must contain 1..{_MAX_CASES} entries")
        return None
    adapter_ids = set(runtime)
    validated: list[dict[str, Any]] = []
    case_ids: set[str] = set()
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            errors.append(f"case {index} must be an object")
            continue
        if not _check_exact_fields(
            case,
            _INTEROPERABILITY_CASE_FIELDS,
            f"case {index}",
            errors,
        ):
            continue
        case_id = case["case_id"]
        if not isinstance(case_id, str) or not case_id or case_id in case_ids:
            errors.append(f"case {index} has invalid or duplicate case_id")
        else:
            case_ids.add(case_id)
        if not _looks_like_sha256(case["artifact_sha256"]):
            errors.append(f"case {index} artifact_sha256 is invalid")
        if type(case["byte_length"]) is not int or case["byte_length"] < 0:
            errors.append(f"case {index} byte_length must be a non-negative integer")
        observations = case["observations"]
        if not isinstance(observations, list) or not observations:
            errors.append(f"case {index} observations must be a non-empty array")
            continue
        seen: set[str] = set()
        for obs_index, observation in enumerate(observations):
            if not isinstance(observation, dict):
                errors.append(f"case {index} observation {obs_index} must be an object")
                continue
            if not _check_exact_fields(
                observation,
                _OBSERVATION_FIELDS,
                f"case {index} observation {obs_index}",
                errors,
            ):
                continue
            adapter_id = observation["adapter_id"]
            if (
                not isinstance(adapter_id, str)
                or adapter_id not in adapter_ids
                or adapter_id in seen
            ):
                errors.append(
                    f"case {index} observation {obs_index} has invalid adapter_id"
                )
                continue
            seen.add(adapter_id)
            if type(observation["supported"]) is not bool:
                errors.append(
                    f"case {index} observation {obs_index} supported must be boolean"
                )
            if observation["supported"]:
                if (
                    type(observation["detected"]) is not bool
                    or not _is_rate(observation["confidence"], nullable=False)
                ):
                    errors.append(
                        f"case {index} observation {obs_index} has invalid supported result"
                    )
            elif (
                observation["detected"] is not None
                or observation["confidence"] is not None
            ):
                errors.append(
                    f"case {index} observation {obs_index} unsupported result must not "
                    "claim detection/confidence"
                )
        if seen != adapter_ids:
            errors.append(
                f"case {index} observations do not match adapter_runtime adapters"
            )
        validated.append(case)
    return validated if len(validated) == len(cases) else None


def _pair_metrics(
    cases: list[dict[str, Any]],
    left: str,
    right: str,
) -> dict[str, Any]:
    comparable = agreements = disagreements = both_detected = both_not = 0
    for case in cases:
        observations = {
            observation["adapter_id"]: observation
            for observation in case["observations"]
        }
        left_observation = observations[left]
        right_observation = observations[right]
        if not left_observation["supported"] or not right_observation["supported"]:
            continue
        comparable += 1
        if left_observation["detected"] == right_observation["detected"]:
            agreements += 1
            if left_observation["detected"]:
                both_detected += 1
            else:
                both_not += 1
        else:
            disagreements += 1
    return {
        "left_adapter_id": left,
        "right_adapter_id": right,
        "comparable_cases": comparable,
        "detection_agreements": agreements,
        "detection_disagreements": disagreements,
        "agreement_rate": agreements / comparable if comparable else None,
        "both_detected": both_detected,
        "both_not_detected": both_not,
    }


def _validate_pairs(
    cases: list[dict[str, Any]],
    runtime: dict[str, Any],
    pairs: Any,
    errors: list[str],
    checks: list[str],
) -> None:
    expected_keys = {
        tuple(sorted(pair))
        for pair in combinations(runtime.keys(), 2)
    }
    if not isinstance(pairs, list) or len(pairs) != len(expected_keys):
        errors.append("pairs must contain exactly one entry for every adapter pair")
        return
    seen: set[tuple[str, str]] = set()
    pair_error_count = len(errors)
    for index, pair in enumerate(pairs):
        if not isinstance(pair, dict):
            errors.append(f"pair {index} must be an object")
            continue
        if not _check_exact_fields(pair, _PAIR_FIELDS, f"pair {index}", errors):
            continue
        left = pair["left_adapter_id"]
        right = pair["right_adapter_id"]
        if (
            not isinstance(left, str)
            or not isinstance(right, str)
            or left == right
        ):
            errors.append(f"pair {index} has invalid adapter ids")
            continue
        key = tuple(sorted((left, right)))
        if key not in expected_keys or key in seen:
            errors.append(f"pair {index} is unknown or duplicated")
            continue
        seen.add(key)
        expected = _pair_metrics(cases, left, right)
        for name in (
            "comparable_cases",
            "detection_agreements",
            "detection_disagreements",
            "both_detected",
            "both_not_detected",
        ):
            if type(pair[name]) is not int or pair[name] != expected[name]:
                errors.append(f"pair {index} {name} does not match cases")
                break
        else:
            if not _same_rate(expected["agreement_rate"], pair["agreement_rate"]):
                errors.append(f"pair {index} agreement_rate does not match cases")
    if seen == expected_keys and len(errors) == pair_error_count:
        checks.extend(("pairs", "pair_semantics"))


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
        _RELIABILITY_FIELDS
        if benchmark_type == "reliability"
        else _INTEROPERABILITY_FIELDS
    )
    if _check_exact_fields(
        payload,
        expected_fields,
        f"{benchmark_type} report",
        errors,
    ):
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
        cases = _validate_reliability_cases(payload.get("cases"), errors)
        if cases is not None:
            checks.append("cases")
            _validate_reliability_summary(
                cases,
                payload.get("summary"),
                errors,
                checks,
            )
    else:
        for field in ("matrix_id", "matrix_version"):
            value = payload.get(field)
            if not isinstance(value, str) or not value:
                errors.append(f"{field} must be a non-empty string")
        if not _looks_like_sha256(payload.get("matrix_digest")):
            errors.append("matrix_digest is not a lowercase SHA-256 digest")
        else:
            checks.append("matrix_digest")
        if not isinstance(runtime, dict) or not 2 <= len(runtime) <= _MAX_ADAPTERS:
            errors.append(
                f"adapter_runtime must contain 2..{_MAX_ADAPTERS} adapters"
            )
        elif any(
            not isinstance(adapter_id, str)
            or not adapter_id
            or not _runtime_list_valid(identity)
            for adapter_id, identity in runtime.items()
        ):
            errors.append("adapter_runtime contains invalid runtime identities")
        else:
            checks.append("adapter_runtime")
            cases = _validate_interop_cases(payload.get("cases"), runtime, errors)
            if cases is not None:
                checks.append("cases")
                _validate_pairs(
                    cases,
                    runtime,
                    payload.get("pairs"),
                    errors,
                    checks,
                )

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
