from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .digests import content_digest, sha256_bytes
from .models import Artifact, DetectionResult
from .registry import AdapterRegistry
from .runtime import adapter_runtime_identity

_MAX_RUNTIME_ITEMS = 16
_MAX_RUNTIME_ITEM_LENGTH = 512


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
