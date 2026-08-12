from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .bindings import BindingExtractionEvidence, ExtractedSoftBinding
from .digests import content_digest
from .manifest_fetch import FetchedManifestStore
from .resolvers import ManifestReference, ResolverResult


class RecoveryError(ValueError):
    """Raised when extraction, resolution, and retrieval evidence do not form one chain."""


@dataclass(frozen=True, slots=True)
class RecoveryCandidate:
    manifest_id: str
    endpoint: str | None
    similarity_score: int | None
    fetched_manifest_sha256: str | None = None
    fetched_manifest_byte_length: int | None = None
    fetched_manifest_media_type: str | None = None

    def __post_init__(self) -> None:
        fetched = (
            self.fetched_manifest_sha256,
            self.fetched_manifest_byte_length,
            self.fetched_manifest_media_type,
        )
        if any(item is not None for item in fetched) and not all(
            item is not None for item in fetched
        ):
            raise RecoveryError("fetched manifest reference must be complete or absent")
        if self.fetched_manifest_sha256 is not None and (
            len(self.fetched_manifest_sha256) != 64
            or any(char not in "0123456789abcdef" for char in self.fetched_manifest_sha256)
        ):
            raise RecoveryError("fetched manifest sha256 must be a lowercase SHA-256 digest")
        if self.fetched_manifest_byte_length is not None and self.fetched_manifest_byte_length < 0:
            raise RecoveryError("fetched manifest byte length must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_id": self.manifest_id,
            "endpoint": self.endpoint,
            "similarity_score": self.similarity_score,
            "fetched_manifest": (
                {
                    "sha256": self.fetched_manifest_sha256,
                    "byte_length": self.fetched_manifest_byte_length,
                    "media_type": self.fetched_manifest_media_type,
                }
                if self.fetched_manifest_sha256 is not None
                else None
            ),
        }


@dataclass(frozen=True, slots=True)
class RecoveryChain:
    artifact_sha256: str
    artifact_byte_length: int
    media_type: str
    extractor_id: str
    binding_kind: str
    binding_algorithm: str
    binding_query_digest: str
    binding_value_length: int
    resolver_id: str
    candidates: tuple[RecoveryCandidate, ...]
    warnings: tuple[str, ...] = ()
    verification_status: str = "candidate_only"
    schema_version: str = "0.1"

    def __post_init__(self) -> None:
        if self.verification_status != "candidate_only":
            raise RecoveryError(
                "recovery chain v0.1 records candidates only; cryptographic verification is separate"
            )

    def core_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "artifact": {
                "sha256": self.artifact_sha256,
                "byte_length": self.artifact_byte_length,
                "media_type": self.media_type,
            },
            "binding": {
                "extractor_id": self.extractor_id,
                "kind": self.binding_kind,
                "algorithm": self.binding_algorithm,
                "query_digest": self.binding_query_digest,
                "value_length": self.binding_value_length,
            },
            "resolver_id": self.resolver_id,
            "verification_status": self.verification_status,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "warnings": list(self.warnings),
        }

    @property
    def recovery_id(self) -> str:
        return content_digest(self.core_dict())

    def to_dict(self) -> dict[str, Any]:
        return {"recovery_id": self.recovery_id, **self.core_dict()}


def _candidate_from_reference(
    reference: ManifestReference,
    fetched: FetchedManifestStore | None,
) -> RecoveryCandidate:
    if fetched is not None:
        if fetched.manifest_id != reference.manifest_id:
            raise RecoveryError("fetched manifest_id does not match selected resolver candidate")
        if reference.endpoint is not None and fetched.endpoint != reference.endpoint:
            raise RecoveryError("fetched manifest endpoint does not match selected resolver candidate")
        return RecoveryCandidate(
            manifest_id=reference.manifest_id,
            endpoint=reference.endpoint or fetched.endpoint,
            similarity_score=reference.similarity_score,
            fetched_manifest_sha256=fetched.sha256,
            fetched_manifest_byte_length=len(fetched.data),
            fetched_manifest_media_type=fetched.media_type,
        )
    return RecoveryCandidate(
        manifest_id=reference.manifest_id,
        endpoint=reference.endpoint,
        similarity_score=reference.similarity_score,
    )


def build_recovery_chain(
    extraction: BindingExtractionEvidence,
    extracted: ExtractedSoftBinding,
    resolution: ResolverResult,
    *,
    fetched_by_manifest_id: dict[str, FetchedManifestStore] | None = None,
) -> RecoveryChain:
    if extracted not in extraction.bindings:
        raise RecoveryError("selected binding is not part of the supplied extraction evidence")
    if resolution.binding_algorithm != extracted.binding.algorithm:
        raise RecoveryError("resolver binding algorithm does not match extracted binding")
    if resolution.query_digest != extracted.binding.query_digest:
        raise RecoveryError("resolver query digest does not match extracted binding")

    fetched_by_manifest_id = fetched_by_manifest_id or {}
    known_ids = {reference.manifest_id for reference in resolution.matches}
    extras = sorted(set(fetched_by_manifest_id) - known_ids)
    if extras:
        raise RecoveryError(
            "fetched manifests do not correspond to resolver candidates: " + ", ".join(extras)
        )

    candidates = tuple(
        _candidate_from_reference(
            reference,
            fetched_by_manifest_id.get(reference.manifest_id),
        )
        for reference in resolution.matches
    )
    return RecoveryChain(
        artifact_sha256=extraction.artifact_sha256,
        artifact_byte_length=extraction.artifact_byte_length,
        media_type=extraction.media_type,
        extractor_id=extracted.extractor_id,
        binding_kind=extracted.kind.value,
        binding_algorithm=extracted.binding.algorithm,
        binding_query_digest=extracted.binding.query_digest,
        binding_value_length=len(extracted.binding.value),
        resolver_id=resolution.resolver_id,
        candidates=candidates,
        warnings=resolution.warnings,
    )
