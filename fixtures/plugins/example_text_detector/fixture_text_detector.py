from __future__ import annotations

from defeat_watermarker.adapters.base import WatermarkAdapter
from defeat_watermarker.models import Artifact, DetectionResult, MarkFamily, Modality

_MARKER = b"DefeatWatermarker UI testing"


class FixtureTextDetector(WatermarkAdapter):
    """Synthetic detector proving the provider-plugin contract in regression tests only."""

    adapter_id = "fixture.text-marker.v1"
    family = MarkFamily.UNKNOWN
    modalities = frozenset({Modality.TEXT})

    def detect(self, artifact: Artifact) -> DetectionResult:
        detected = _MARKER in artifact.data
        return DetectionResult(
            adapter_id=self.adapter_id,
            family=self.family,
            detected=detected,
            confidence=1.0 if detected else 0.0,
            evidence=("synthetic-fixture-marker=v1",) if detected else (),
            warnings=(
                "Synthetic regression detector only; not a production watermark detector.",
            ),
        )
