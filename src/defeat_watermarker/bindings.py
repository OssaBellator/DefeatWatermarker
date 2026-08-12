from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .digests import sha256_bytes
from .models import Artifact, Modality
from .resolvers import SoftBinding

_MAX_BINDINGS_PER_EXTRACTOR = 32


class BindingError(ValueError):
    """Raised when a soft-binding extractor violates the bounded interface."""


class SoftBindingKind(str, Enum):
    WATERMARK = "watermark"
    FINGERPRINT = "fingerprint"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class ExtractedSoftBinding:
    extractor_id: str
    kind: SoftBindingKind
    binding: SoftBinding

    def reference_dict(self) -> dict[str, Any]:
        return {
            "extractor_id": self.extractor_id,
            "kind": self.kind.value,
            **self.binding.reference_dict(),
        }


@dataclass(frozen=True, slots=True)
class BindingExtractionEvidence:
    artifact_sha256: str
    artifact_byte_length: int
    media_type: str
    bindings: tuple[ExtractedSoftBinding, ...]
    schema_version: str = "0.1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "artifact_sha256": self.artifact_sha256,
            "artifact_byte_length": self.artifact_byte_length,
            "media_type": self.media_type,
            "bindings": [item.reference_dict() for item in self.bindings],
        }


class SoftBindingExtractor(ABC):
    """Extract candidate durable-provenance bindings without resolving them."""

    extractor_id: str
    kind: SoftBindingKind
    modalities: frozenset[Modality]

    def supports(self, artifact: Artifact) -> bool:
        return Modality.UNKNOWN in self.modalities or artifact.modality in self.modalities

    @abstractmethod
    def extract(self, artifact: Artifact) -> tuple[SoftBinding, ...]:
        raise NotImplementedError


class BindingExtractorRegistry:
    def __init__(self, extractors: Iterable[SoftBindingExtractor] = ()) -> None:
        self._extractors: dict[str, SoftBindingExtractor] = {}
        for extractor in extractors:
            self.register(extractor)

    def register(self, extractor: SoftBindingExtractor) -> None:
        if not extractor.extractor_id or len(extractor.extractor_id) > 128:
            raise BindingError("extractor_id is missing or too long")
        if extractor.extractor_id in self._extractors:
            raise BindingError(f"duplicate extractor_id: {extractor.extractor_id}")
        self._extractors[extractor.extractor_id] = extractor

    def get(self, extractor_id: str) -> SoftBindingExtractor:
        try:
            return self._extractors[extractor_id]
        except KeyError as exc:
            raise BindingError(f"unknown extractor_id: {extractor_id}") from exc

    def __iter__(self) -> Iterator[SoftBindingExtractor]:
        return iter(self._extractors.values())


def extract_soft_bindings(
    artifact: Artifact,
    registry: BindingExtractorRegistry,
) -> BindingExtractionEvidence:
    extracted: list[ExtractedSoftBinding] = []
    for extractor in registry:
        if not extractor.supports(artifact):
            continue
        bindings = tuple(extractor.extract(artifact))
        if len(bindings) > _MAX_BINDINGS_PER_EXTRACTOR:
            raise BindingError(
                f"extractor {extractor.extractor_id} exceeded "
                f"{_MAX_BINDINGS_PER_EXTRACTOR} bindings"
            )
        extracted.extend(
            ExtractedSoftBinding(
                extractor_id=extractor.extractor_id,
                kind=extractor.kind,
                binding=binding,
            )
            for binding in bindings
        )
    return BindingExtractionEvidence(
        artifact_sha256=sha256_bytes(artifact.data),
        artifact_byte_length=len(artifact.data),
        media_type=artifact.media_type,
        bindings=tuple(extracted),
    )
