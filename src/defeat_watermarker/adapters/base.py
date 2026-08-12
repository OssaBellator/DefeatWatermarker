from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from ..models import Artifact, DetectionResult, MarkFamily, Modality


class WatermarkAdapter(ABC):
    """Read-only adapter for one watermark/provenance detection mechanism."""

    adapter_id: str
    family: MarkFamily
    modalities: frozenset[Modality]

    def supports(self, artifact: Artifact) -> bool:
        return Modality.UNKNOWN in self.modalities or artifact.modality in self.modalities

    @abstractmethod
    def detect(self, artifact: Artifact) -> DetectionResult:
        """Inspect an artifact without modifying it."""
        raise NotImplementedError

    def capabilities(self) -> Iterable[str]:
        return ("detect",)
