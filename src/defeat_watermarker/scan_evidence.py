from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .digests import content_digest, sha256_bytes
from .models import Artifact, DetectionResult
from .registry import AdapterRegistry
from .runtime import adapter_runtime_identity

_MAX_RUNTIME_ITEMS = 16
_MAX_RUNTIME_ITEM_LENGTH = 512
_MAX_SCAN_BYTES = 20 * 1024 * 1024
_SHA256_LENGTH = 64


class ScanEvidenceError(ValueError):
    """Raised when scan evidence is malformed or exceeds bounded input limits."""


@dataclass(frozen=True, slots=True)
class ScanEvidence:
    artifact_name: str
    artifact_sha256: str
    artifact_byte_length: int
    media_type: str
    modality: str
    results: tuple[DetectionResult, ...]
    adapter_runtime: tuple[tuple[str, tuple[str, ...]], ...]
    schema_version: str = "0.1"

    def core_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "artifact": {
                "name": self.artifact_name,
                "sha256": self.artifact_sha256,
                "byte_length": self.artifact_byte_length,
                "media_type": self.media_type,
                "modality": self.modality,
            },
            "adapter_runtime": {
                adapter_id: list(identity)
                for adapter_id, identity in self.adapter_runtime
            },
            "results": [item.to_dict() for item in self.results],
        }

    @property
    def scan_id(self) -> str:
        return content_digest(self.core_dict())

    def to_dict(self) -> dict[str, Any]:
        return {"scan_id": self.scan_id, **self.core_dict()}


@dataclass(frozen=True, slots=True)
class ScanVerificationResult:
    valid: bool
    scan_id: str | None
    checks: tuple[str, ...]
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "scan_id": self.scan_id,
            "checks": list(self.checks),
            "errors": list(self.errors),
        }


def _bounded_runtime_identity(adapter: Any) -> tuple[str, ...]:
    identity = tuple(adapter_runtime_identity(adapter))
    if len(identity) > _MAX_RUNTIME_ITEMS:
        raise ValueError(f"adapter {adapter.adapter_id} returned too many runtime identity items")
    if any(len(item) > _MAX_RUNTIME_ITEM_LENGTH for item in identity):
        raise ValueError(f"adapter {adapter.adapter_id} returned an oversized runtime identity item")
    return identity


def build_scan_evidence(artifact: Artifact, registry: AdapterRegistry) -> ScanEvidence:
    results: list[DetectionResult] = []
    runtime: list[tuple[str, tuple[str, ...]]] = []
    for adapter in registry:
        if not adapter.supports(artifact):
            continue
        runtime.append((adapter.adapter_id, _bounded_runtime_identity(adapter)))
        result = adapter.detect(artifact)
        if result.adapter_id != adapter.adapter_id:
            raise ValueError(
                f"adapter {adapter.adapter_id} returned mismatched result id {result.adapter_id}"
            )
        results.append(result)

    return ScanEvidence(
        artifact_name=artifact.name,
        artifact_sha256=sha256_bytes(artifact.data),
        artifact_byte_length=len(artifact.data),
        media_type=artifact.media_type,
        modality=artifact.modality.value,
        results=tuple(results),
        adapter_runtime=tuple(runtime),
    )


def _looks_like_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == _SHA256_LENGTH
        and all(character in "0123456789abcdef" for character in value)
    )


def verify_scan_document(payload: dict[str, Any]) -> ScanVerificationResult:
    required = {
        "scan_id",
        "schema_version",
        "artifact",
        "adapter_runtime",
        "results",
    }
    checks: list[str] = []
    errors: list[str] = []
    if set(payload) != required:
        missing = sorted(required - set(payload))
        extras = sorted(set(payload) - required)
        if missing:
            errors.append(f"missing fields: {', '.join(missing)}")
        if extras:
            errors.append(f"unknown fields: {', '.join(extras)}")
        return ScanVerificationResult(False, None, tuple(checks), tuple(errors))

    if payload.get("schema_version") != "0.1":
        errors.append("unsupported scan schema_version")
    else:
        checks.append("schema_version")

    scan_id = payload.get("scan_id")
    if not _looks_like_sha256(scan_id):
        errors.append("scan_id is not a lowercase SHA-256 digest")
    else:
        core = {key: value for key, value in payload.items() if key != "scan_id"}
        if content_digest(core) != scan_id:
            errors.append("scan_id does not match scan evidence core")
        else:
            checks.append("scan_id")

    artifact = payload.get("artifact")
    artifact_keys = {"name", "sha256", "byte_length", "media_type", "modality"}
    if not isinstance(artifact, dict) or set(artifact) != artifact_keys:
        errors.append("artifact reference has invalid fields")
    elif not _looks_like_sha256(artifact.get("sha256")):
        errors.append("artifact reference is missing a valid SHA-256 digest")
    elif type(artifact.get("byte_length")) is not int or artifact["byte_length"] < 0:
        errors.append("artifact byte_length must be a non-negative integer")
    else:
        checks.append("artifact_reference")

    runtime = payload.get("adapter_runtime")
    if not isinstance(runtime, dict):
        errors.append("adapter_runtime must be an object")
    else:
        runtime_valid = True
        for adapter_id, identity in runtime.items():
            if not isinstance(adapter_id, str) or not adapter_id:
                runtime_valid = False
                break
            if not isinstance(identity, list) or len(identity) > _MAX_RUNTIME_ITEMS:
                runtime_valid = False
                break
            if any(
                not isinstance(item, str) or len(item) > _MAX_RUNTIME_ITEM_LENGTH
                for item in identity
            ):
                runtime_valid = False
                break
        if runtime_valid:
            checks.append("adapter_runtime")
        else:
            errors.append("adapter_runtime contains invalid or unbounded identity data")

    results = payload.get("results")
    if not isinstance(results, list):
        errors.append("results must be an array")
    elif any(not isinstance(item, dict) for item in results):
        errors.append("results must contain objects")
    else:
        checks.append("results")

    return ScanVerificationResult(
        valid=not errors,
        scan_id=scan_id if isinstance(scan_id, str) else None,
        checks=tuple(checks),
        errors=tuple(errors),
    )


def load_scan_document(path: Path) -> dict[str, Any]:
    if path.stat().st_size > _MAX_SCAN_BYTES:
        raise ScanEvidenceError(f"scan evidence file exceeds {_MAX_SCAN_BYTES} bytes")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ScanEvidenceError(f"could not read scan evidence: {exc}") from exc
    if not isinstance(payload, dict):
        raise ScanEvidenceError("scan evidence document must be a JSON object")
    return payload
