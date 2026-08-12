from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .adapters.base import WatermarkAdapter
from .digests import content_digest, sha256_bytes
from .models import Artifact, DetectionResult
from .runtime import adapter_runtime_identity

_MAX_CONFORMANCE_BYTES = 2 * 1024 * 1024
_MAX_CHECKS = 32
_MAX_ERRORS = 32
_MAX_ERROR_LENGTH = 1024
_MAX_RUNTIME_ITEMS = 32
_MAX_RUNTIME_ITEM_LENGTH = 512
_MAX_DETECTION_ITEMS = 128
_MAX_DETECTION_ITEM_LENGTH = 2048
_REQUIRED_PASS_CHECKS = {
    "runtime_identity",
    "read_only_capability",
    "supports_artifact",
    "adapter_id_match",
    "family_match",
    "deterministic_detection",
    "source_unchanged",
}
_DETECTION_FIELDS = {
    "adapter_id",
    "family",
    "detected",
    "confidence",
    "evidence",
    "warnings",
    "provenance_identifier",
    "cryptographically_verified",
    "registry_verified",
    "verification_state",
    "validation_codes",
    "provenance_graph",
}


@dataclass(frozen=True, slots=True)
class DetectorConformanceReport:
    plugin_name: str
    adapter_id: str
    artifact_sha256: str
    artifact_byte_length: int
    media_type: str
    modality: str
    runtime_identity: tuple[str, ...]
    passed: bool
    checks: tuple[str, ...]
    errors: tuple[str, ...]
    detection: dict[str, Any] | None
    schema_version: str = "0.1"

    def core_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "plugin_name": self.plugin_name,
            "adapter_id": self.adapter_id,
            "artifact": {
                "sha256": self.artifact_sha256,
                "byte_length": self.artifact_byte_length,
                "media_type": self.media_type,
                "modality": self.modality,
            },
            "runtime_identity": list(self.runtime_identity),
            "passed": self.passed,
            "checks": list(self.checks),
            "errors": list(self.errors),
            "detection": self.detection,
        }

    @property
    def report_id(self) -> str:
        return content_digest(self.core_dict())

    def to_dict(self) -> dict[str, Any]:
        return {"report_id": self.report_id, **self.core_dict()}


@dataclass(frozen=True, slots=True)
class DetectorConformanceVerification:
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


def run_detector_conformance(
    plugin_name: str,
    adapter: WatermarkAdapter,
    artifact: Artifact,
) -> DetectorConformanceReport:
    checks: list[str] = []
    errors: list[str] = []
    runtime: tuple[str, ...] = ()
    before = sha256_bytes(artifact.data)

    try:
        first_runtime = adapter_runtime_identity(adapter)
        second_runtime = adapter_runtime_identity(adapter)
        if first_runtime != second_runtime:
            errors.append("adapter runtime identity is not deterministic")
        else:
            runtime = first_runtime
            checks.append("runtime_identity")
    except Exception as exc:
        errors.append(f"runtime identity failed: {exc}"[:_MAX_ERROR_LENGTH])

    try:
        capabilities = tuple(adapter.capabilities())
        if not capabilities or any(
            not isinstance(item, str) or not item for item in capabilities
        ):
            errors.append("adapter capabilities are invalid")
        elif "detect" not in capabilities:
            errors.append("adapter does not declare detect capability")
        elif "remove" in capabilities or callable(getattr(adapter, "remove", None)):
            errors.append("adapter exposes a removal capability")
        else:
            checks.append("read_only_capability")
    except Exception as exc:
        errors.append(f"capability inspection failed: {exc}"[:_MAX_ERROR_LENGTH])

    detection: dict[str, Any] | None = None
    if not adapter.supports(artifact):
        errors.append("adapter does not support the supplied artifact modality")
    else:
        checks.append("supports_artifact")
        try:
            first = adapter.detect(artifact)
            second = adapter.detect(artifact)
            if not isinstance(first, DetectionResult) or not isinstance(
                second, DetectionResult
            ):
                errors.append("adapter detect() did not return DetectionResult")
            else:
                detection = first.to_dict()
                if first.adapter_id != adapter.adapter_id:
                    errors.append("detection adapter_id does not match adapter")
                else:
                    checks.append("adapter_id_match")
                if first.family != adapter.family:
                    errors.append("detection family does not match adapter")
                else:
                    checks.append("family_match")
                if first.to_dict() != second.to_dict():
                    errors.append(
                        "adapter detection is not deterministic for identical input"
                    )
                else:
                    checks.append("deterministic_detection")
        except Exception as exc:
            errors.append(f"detection failed: {exc}"[:_MAX_ERROR_LENGTH])

    if sha256_bytes(artifact.data) != before:
        errors.append("source artifact bytes changed during conformance check")
    else:
        checks.append("source_unchanged")

    if len(checks) > _MAX_CHECKS or len(errors) > _MAX_ERRORS:
        raise ValueError("conformance result exceeded internal evidence bounds")

    return DetectorConformanceReport(
        plugin_name=plugin_name,
        adapter_id=adapter.adapter_id,
        artifact_sha256=before,
        artifact_byte_length=len(artifact.data),
        media_type=artifact.media_type,
        modality=artifact.modality.value,
        runtime_identity=runtime,
        passed=not errors,
        checks=tuple(checks),
        errors=tuple(errors),
        detection=detection,
    )


def _validate_detection(
    value: Any,
    adapter_id: str,
    errors: list[str],
) -> bool:
    if not isinstance(value, dict) or set(value) != _DETECTION_FIELDS:
        errors.append("detection evidence has invalid fields")
        return False
    if value.get("adapter_id") != adapter_id:
        errors.append("detection adapter_id does not match report adapter_id")
        return False
    if not isinstance(value.get("family"), str) or not value["family"]:
        errors.append("detection family is invalid")
        return False
    if type(value.get("detected")) is not bool:
        errors.append("detection detected must be boolean")
        return False
    confidence = value.get("confidence")
    if (
        not isinstance(confidence, (int, float))
        or isinstance(confidence, bool)
        or not 0.0 <= float(confidence) <= 1.0
    ):
        errors.append("detection confidence must be between 0 and 1")
        return False
    for name in ("evidence", "warnings", "validation_codes"):
        items = value.get(name)
        if (
            not isinstance(items, list)
            or len(items) > _MAX_DETECTION_ITEMS
            or any(
                not isinstance(item, str)
                or len(item) > _MAX_DETECTION_ITEM_LENGTH
                for item in items
            )
        ):
            errors.append(f"detection {name} is invalid or unbounded")
            return False
    provenance_identifier = value.get("provenance_identifier")
    if provenance_identifier is not None and (
        not isinstance(provenance_identifier, str)
        or len(provenance_identifier) > _MAX_DETECTION_ITEM_LENGTH
    ):
        errors.append("detection provenance_identifier is invalid or unbounded")
        return False
    for name in ("cryptographically_verified", "registry_verified"):
        if type(value.get(name)) is not bool:
            errors.append(f"detection {name} must be boolean")
            return False
    if (
        not isinstance(value.get("verification_state"), str)
        or not value["verification_state"]
    ):
        errors.append("detection verification_state is invalid")
        return False
    if value.get("provenance_graph") is not None and not isinstance(
        value["provenance_graph"], dict
    ):
        errors.append("detection provenance_graph must be an object or null")
        return False
    return True


def verify_conformance_document(
    payload: dict[str, Any],
) -> DetectorConformanceVerification:
    required = {
        "report_id",
        "schema_version",
        "plugin_name",
        "adapter_id",
        "artifact",
        "runtime_identity",
        "passed",
        "checks",
        "errors",
        "detection",
    }
    checks: list[str] = []
    errors: list[str] = []
    if set(payload) != required:
        missing = sorted(required - set(payload))
        extra = sorted(set(payload) - required)
        if missing:
            errors.append("missing fields: " + ", ".join(missing))
        if extra:
            errors.append("unknown fields: " + ", ".join(extra))
        return DetectorConformanceVerification(False, None, (), tuple(errors))

    report_id = payload.get("report_id")
    if not _is_sha256(report_id):
        errors.append("report_id is not a lowercase SHA-256 digest")
    else:
        core = {key: value for key, value in payload.items() if key != "report_id"}
        if content_digest(core) != report_id:
            errors.append("report_id does not match conformance report core")
        else:
            checks.append("report_id")

    if payload.get("schema_version") != "0.1":
        errors.append("unsupported conformance schema_version")
    else:
        checks.append("schema_version")

    for field in ("plugin_name", "adapter_id"):
        value = payload.get(field)
        if not isinstance(value, str) or not value or len(value) > 128:
            errors.append(f"{field} must be a bounded non-empty string")

    artifact = payload.get("artifact")
    if not isinstance(artifact, dict) or set(artifact) != {
        "sha256",
        "byte_length",
        "media_type",
        "modality",
    }:
        errors.append("artifact reference has invalid fields")
    elif not _is_sha256(artifact.get("sha256")):
        errors.append("artifact reference has invalid sha256")
    elif type(artifact.get("byte_length")) is not int or artifact["byte_length"] < 0:
        errors.append("artifact byte_length must be a non-negative integer")
    elif any(
        not isinstance(artifact.get(name), str) or not artifact[name]
        for name in ("media_type", "modality")
    ):
        errors.append("artifact media_type/modality must be non-empty strings")
    else:
        checks.append("artifact_reference")

    runtime = payload.get("runtime_identity")
    if (
        not isinstance(runtime, list)
        or not 1 <= len(runtime) <= _MAX_RUNTIME_ITEMS
        or any(
            not isinstance(item, str)
            or not item
            or len(item) > _MAX_RUNTIME_ITEM_LENGTH
            or "\n" in item
            or "\r" in item
            for item in runtime
        )
    ):
        errors.append("runtime_identity is invalid or unbounded")
    else:
        checks.append("runtime_identity")

    report_checks = payload.get("checks")
    report_errors = payload.get("errors")
    if (
        not isinstance(report_checks, list)
        or len(report_checks) > _MAX_CHECKS
        or any(not isinstance(item, str) or not item for item in report_checks)
    ):
        errors.append("checks are invalid or unbounded")
    if (
        not isinstance(report_errors, list)
        or len(report_errors) > _MAX_ERRORS
        or any(
            not isinstance(item, str)
            or not item
            or len(item) > _MAX_ERROR_LENGTH
            for item in report_errors
        )
    ):
        errors.append("errors are invalid or unbounded")

    passed = payload.get("passed")
    if type(passed) is not bool:
        errors.append("passed must be boolean")
    elif isinstance(report_errors, list) and passed != (len(report_errors) == 0):
        errors.append("passed does not match conformance errors")
    elif passed:
        if not isinstance(report_checks, list) or not _REQUIRED_PASS_CHECKS.issubset(
            report_checks
        ):
            errors.append("passing conformance report is missing required checks")
        if _validate_detection(
            payload.get("detection"), str(payload.get("adapter_id")), errors
        ):
            checks.append("status_semantics")
    elif payload.get("detection") is not None and not isinstance(
        payload.get("detection"), dict
    ):
        errors.append("detection must be an object or null")

    return DetectorConformanceVerification(
        valid=not errors,
        report_id=report_id if isinstance(report_id, str) else None,
        checks=tuple(checks),
        errors=tuple(errors),
    )


def load_conformance_document(path: Path) -> dict[str, Any]:
    if path.stat().st_size > _MAX_CONFORMANCE_BYTES:
        raise ValueError(
            f"conformance report exceeds {_MAX_CONFORMANCE_BYTES} bytes"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read conformance report: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("conformance report must be a JSON object")
    return payload
