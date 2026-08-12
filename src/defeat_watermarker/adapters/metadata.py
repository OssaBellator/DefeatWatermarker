from __future__ import annotations

from ..models import Artifact, DetectionResult, MarkFamily, Modality
from .base import WatermarkAdapter


class ContainerHintAdapter(WatermarkAdapter):
    """Conservative byte-level discovery of common provenance/container hints.

    This adapter is intentionally not a C2PA verifier. It identifies candidate
    strings that justify deeper parsing by a future standards-aware adapter.
    """

    adapter_id = "builtin.container-hints.v1"
    family = MarkFamily.METADATA
    modalities = frozenset({Modality.UNKNOWN})

    _MARKERS: tuple[tuple[bytes, str], ...] = (
        (b"c2pa", "C2PA marker"),
        (b"content credentials", "Content Credentials marker"),
        (b"xmpmeta", "XMP metadata marker"),
        (b"provenance", "provenance marker"),
    )

    def detect(self, artifact: Artifact) -> DetectionResult:
        lowered = artifact.data.lower()
        evidence = tuple(label for marker, label in self._MARKERS if marker in lowered)
        detected = bool(evidence)
        return DetectionResult(
            adapter_id=self.adapter_id,
            family=self.family,
            detected=detected,
            confidence=0.65 if detected else 0.0,
            evidence=evidence,
            warnings=(
                "Container hints are discovery signals only; cryptographic provenance was not verified.",
            ) if detected else (),
        )
