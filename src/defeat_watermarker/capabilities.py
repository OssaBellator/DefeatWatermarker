from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .adapters.c2pa import C2paPythonBackend
from .models import MarkFamily, Modality
from .mutations.image import pillow_available
from .mutations.video import ffmpeg_available


@dataclass(frozen=True, slots=True)
class ComponentCapability:
    component_id: str
    component_type: str
    available: bool
    modalities: tuple[Modality, ...]
    family: MarkFamily | None = None
    optional_extra: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "component_type": self.component_type,
            "available": self.available,
            "modalities": [item.value for item in self.modalities],
            "family": self.family.value if self.family is not None else None,
            "optional_extra": self.optional_extra,
            "notes": self.notes,
        }


def builtin_capabilities() -> tuple[ComponentCapability, ...]:
    image_available = pillow_available()
    c2pa_available = C2paPythonBackend.available()
    video_available = ffmpeg_available()
    return (
        ComponentCapability(
            component_id="evidence.content-addressed.v2",
            component_type="framework",
            available=True,
            modalities=(Modality.UNKNOWN,),
            notes="Evidence ID binds artifact reference, suite, report, summary and gate policy/result.",
        ),
        ComponentCapability(
            component_id="evidence.offline-verifier.v1",
            component_type="framework",
            available=True,
            modalities=(Modality.UNKNOWN,),
        ),
        ComponentCapability(
            component_id="suite.detector-blind-fixed.v1",
            component_type="framework",
            available=True,
            modalities=(Modality.UNKNOWN,),
            notes="Mutation selection is independent of detector feedback.",
        ),
        ComponentCapability(
            component_id="metrics.detection-survival.v1",
            component_type="metric",
            available=True,
            modalities=(Modality.UNKNOWN,),
        ),
        ComponentCapability(
            component_id="metrics.provenance-assurance-continuity.v1",
            component_type="metric",
            available=True,
            modalities=(Modality.UNKNOWN,),
        ),
        ComponentCapability(
            component_id="interoperability.matrix-runner.v1",
            component_type="benchmark",
            available=True,
            modalities=(Modality.UNKNOWN,),
            notes="Runs fixed pairwise detector agreement matrices; does not itself prove interoperability.",
        ),
        ComponentCapability(
            component_id="interoperability.matrix.v1",
            component_type="evidence-gap",
            available=False,
            modalities=(Modality.UNKNOWN,),
            notes="Requires representative independent implementations and reviewed interoperability fixtures.",
        ),
        ComponentCapability(
            component_id="reliability.false-positive-negative.v1",
            component_type="benchmark",
            available=True,
            modalities=(Modality.UNKNOWN,),
            notes="Fixed labelled-corpus runner; meaningful claims still require representative reviewed corpora.",
        ),
        ComponentCapability(
            component_id="builtin.container-hints.v1",
            component_type="adapter",
            available=True,
            modalities=(Modality.UNKNOWN,),
            family=MarkFamily.METADATA,
            notes="Discovery hints only; does not cryptographically verify provenance.",
        ),
        ComponentCapability(
            component_id="c2pa.reader.v1",
            component_type="adapter",
            available=c2pa_available,
            modalities=(
                Modality.IMAGE,
                Modality.VIDEO,
                Modality.AUDIO,
                Modality.DOCUMENT,
                Modality.BINARY,
            ),
            family=MarkFamily.SIGNED_PROVENANCE,
            optional_extra="c2pa",
            notes="Official c2pa-python Reader; remote manifest fetching disabled by default.",
        ),
        ComponentCapability(
            component_id="soft-binding.resolver-interface.v1",
            component_type="resolver-interface",
            available=True,
            modalities=(Modality.UNKNOWN,),
            family=MarkFamily.REGISTRY,
            notes="By-binding only; requires explicit endpoint/resource policy; no default network client.",
        ),
        ComponentCapability(
            component_id="control.identity.v1",
            component_type="mutation",
            available=True,
            modalities=(Modality.UNKNOWN,),
        ),
        ComponentCapability(
            component_id="control.byte-copy.v1",
            component_type="mutation",
            available=True,
            modalities=(Modality.UNKNOWN,),
        ),
        ComponentCapability(
            component_id="image.jpeg-reencode.q85.v1",
            component_type="mutation",
            available=image_available,
            modalities=(Modality.IMAGE,),
            optional_extra="image",
        ),
        ComponentCapability(
            component_id="image.resize-75pct.jpeg-q85.v1",
            component_type="mutation",
            available=image_available,
            modalities=(Modality.IMAGE,),
            optional_extra="image",
        ),
        ComponentCapability(
            component_id="image.center-crop-90pct.jpeg-q85.v1",
            component_type="mutation",
            available=image_available,
            modalities=(Modality.IMAGE,),
            optional_extra="image",
        ),
        ComponentCapability(
            component_id="audio.wav-pcm16.gain-minus3db.v1",
            component_type="mutation",
            available=True,
            modalities=(Modality.AUDIO,),
        ),
        ComponentCapability(
            component_id="audio.wav-pcm16.downmix-mono.v1",
            component_type="mutation",
            available=True,
            modalities=(Modality.AUDIO,),
        ),
        ComponentCapability(
            component_id="audio.wav-pcm16.resample-16khz.v1",
            component_type="mutation",
            available=True,
            modalities=(Modality.AUDIO,),
        ),
        ComponentCapability(
            component_id="text.unicode-nfc.v1",
            component_type="mutation",
            available=True,
            modalities=(Modality.TEXT,),
        ),
        ComponentCapability(
            component_id="text.line-endings-lf.v1",
            component_type="mutation",
            available=True,
            modalities=(Modality.TEXT,),
        ),
        ComponentCapability(
            component_id="text.strip-trailing-horizontal-whitespace.v1",
            component_type="mutation",
            available=True,
            modalities=(Modality.TEXT,),
        ),
        ComponentCapability(
            component_id="video.ffmpeg-h264-crf23-aac128.v1",
            component_type="mutation",
            available=video_available,
            modalities=(Modality.VIDEO,),
            notes="Requires ffmpeg on PATH; command is fixed and invoked without a shell.",
        ),
        ComponentCapability(
            component_id="video.ffmpeg-scale75-h264-crf23-aac128.v1",
            component_type="mutation",
            available=video_available,
            modalities=(Modality.VIDEO,),
            notes="Requires ffmpeg on PATH; fixed 75% rendition plus H.264/AAC transcode.",
        ),
    )


def capability_document() -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "components": [item.to_dict() for item in builtin_capabilities()],
    }
