from __future__ import annotations

from defeat_watermarker.adapters.base import WatermarkAdapter
from defeat_watermarker.models import Artifact, DetectionResult, MarkFamily, Modality

_PRIMARY_MARKER = b"DefeatWatermarker UI testing"
_SECONDARY_MARKER = b"DefeatWatermarker secondary detector marker"
_WARNING = "Synthetic regression detector only; not a production watermark detector."


class FixtureTextDetector(WatermarkAdapter):
    """Synthetic primary detector proving the provider-plugin contract in regression tests."""

    adapter_id = "fixture.text-marker.v1"
    family = MarkFamily.UNKNOWN
    modalities = frozenset({Modality.TEXT})

    def detect(self, artifact: Artifact) -> DetectionResult:
        detected = _PRIMARY_MARKER in artifact.data
        return DetectionResult(
            adapter_id=self.adapter_id,
            family=self.family,
            detected=detected,
            confidence=1.0 if detected else 0.0,
            evidence=("synthetic-fixture-marker=v1",) if detected else (),
            warnings=(_WARNING,),
        )


class FixtureSecondaryTextDetector(WatermarkAdapter):
    """Second synthetic detector used only for pairwise interoperability regression tests."""

    adapter_id = "fixture.text-secondary.v1"
    family = MarkFamily.UNKNOWN
    modalities = frozenset({Modality.TEXT})

    def detect(self, artifact: Artifact) -> DetectionResult:
        detected = _SECONDARY_MARKER in artifact.data
        return DetectionResult(
            adapter_id=self.adapter_id,
            family=self.family,
            detected=detected,
            confidence=0.75 if detected else 0.0,
            evidence=("synthetic-secondary-marker=v1",) if detected else (),
            warnings=(_WARNING,),
        )
