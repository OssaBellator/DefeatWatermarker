from __future__ import annotations

from .models import Modality
from .suites import RobustnessSuite, suite_from_dict


_BUILTIN_SUITE_DOCUMENTS: dict[Modality, dict[str, object]] = {
    Modality.IMAGE: {
        "schema_version": "0.1",
        "suite_id": "image-platform-rendition",
        "version": "0.1",
        "description": (
            "Built-in fixed detector-blind image transformations representing ordinary "
            "platform rendition, resizing, cropping, and generational recompression."
        ),
        "scenarios": [
            {
                "scenario_id": "jpeg-q85",
                "mutation_id": "image.jpeg-reencode.q85.v1",
                "modality": "image",
                "transformation_family": "reencode",
                "severity": "low",
                "generation_count": 1,
            },
            {
                "scenario_id": "resize-75-jpeg-q85",
                "mutation_id": "image.resize-75pct.jpeg-q85.v1",
                "modality": "image",
                "transformation_family": "resize",
                "severity": "medium",
                "generation_count": 1,
            },
            {
                "scenario_id": "center-crop-90-jpeg-q85",
                "mutation_id": "image.center-crop-90pct.jpeg-q85.v1",
                "modality": "image",
                "transformation_family": "crop",
                "severity": "medium",
                "generation_count": 1,
            },
            {
                "scenario_id": "jpeg-q85-three-generations",
                "mutation_id": "image.jpeg-reencode.q85.v1",
                "modality": "image",
                "transformation_family": "generational-reencode",
                "severity": "high",
                "generation_count": 3,
            },
        ],
    },
    Modality.AUDIO: {
        "schema_version": "0.1",
        "suite_id": "audio-pcm-workflow",
        "version": "0.1",
        "description": (
            "Built-in fixed detector-blind PCM-WAV processing representing level "
            "adjustment, channel downmix and sample-rate conversion."
        ),
        "scenarios": [
            {
                "scenario_id": "gain-minus3db",
                "mutation_id": "audio.wav-pcm16.gain-minus3db.v1",
                "modality": "audio",
                "transformation_family": "level-adjustment",
                "severity": "low",
                "generation_count": 1,
            },
            {
                "scenario_id": "downmix-mono",
                "mutation_id": "audio.wav-pcm16.downmix-mono.v1",
                "modality": "audio",
                "transformation_family": "channel-conversion",
                "severity": "medium",
                "generation_count": 1,
            },
            {
                "scenario_id": "resample-16khz",
                "mutation_id": "audio.wav-pcm16.resample-16khz.v1",
                "modality": "audio",
                "transformation_family": "sample-rate-conversion",
                "severity": "medium",
                "generation_count": 1,
            },
        ],
    },
    Modality.VIDEO: {
        "schema_version": "0.1",
        "suite_id": "video-platform-rendition",
        "version": "0.1",
        "description": (
            "Built-in fixed detector-blind FFmpeg renditions representing ordinary "
            "H.264/AAC platform transcoding and resolution reduction."
        ),
        "scenarios": [
            {
                "scenario_id": "h264-crf23-aac128",
                "mutation_id": "video.ffmpeg-h264-crf23-aac128.v1",
                "modality": "video",
                "transformation_family": "transcode",
                "severity": "medium",
                "generation_count": 1,
            },
            {
                "scenario_id": "scale75-h264-crf23-aac128",
                "mutation_id": "video.ffmpeg-scale75-h264-crf23-aac128.v1",
                "modality": "video",
                "transformation_family": "scale-and-transcode",
                "severity": "high",
                "generation_count": 1,
            },
        ],
    },
    Modality.TEXT: {
        "schema_version": "0.1",
        "suite_id": "text-editorial-normalization",
        "version": "0.1",
        "description": (
            "Built-in fixed non-semantic text processing representative of ordinary "
            "storage and editor normalization."
        ),
        "scenarios": [
            {
                "scenario_id": "unicode-nfc",
                "mutation_id": "text.unicode-nfc.v1",
                "modality": "text",
                "transformation_family": "unicode-normalization",
                "severity": "low",
                "generation_count": 1,
            },
            {
                "scenario_id": "line-endings-lf",
                "mutation_id": "text.line-endings-lf.v1",
                "modality": "text",
                "transformation_family": "line-ending-normalization",
                "severity": "low",
                "generation_count": 1,
            },
            {
                "scenario_id": "strip-trailing-horizontal-whitespace",
                "mutation_id": "text.strip-trailing-horizontal-whitespace.v1",
                "modality": "text",
                "transformation_family": "editor-cleanup",
                "severity": "low",
                "generation_count": 1,
            },
        ],
    },
}


def builtin_suite_for(modality: Modality) -> RobustnessSuite | None:
    payload = _BUILTIN_SUITE_DOCUMENTS.get(modality)
    if payload is None:
        return None
    return suite_from_dict(payload)


def builtin_suite_catalog() -> tuple[RobustnessSuite, ...]:
    return tuple(
        builtin
        for modality in (Modality.IMAGE, Modality.AUDIO, Modality.VIDEO, Modality.TEXT)
        if (builtin := builtin_suite_for(modality)) is not None
    )
