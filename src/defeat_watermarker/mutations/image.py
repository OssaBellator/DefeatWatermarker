from __future__ import annotations

import importlib.util
import io

from ..models import Artifact, Modality, MutationScenario
from .base import ArtifactMutation


class ImageMutationError(ValueError):
    """Raised when a fixed image workflow transformation cannot be applied."""


def pillow_available() -> bool:
    return importlib.util.find_spec("PIL") is not None


def _prepare_rgb(artifact: Artifact):
    if artifact.modality not in {Modality.IMAGE, Modality.UNKNOWN}:
        raise ImageMutationError("image mutation requires an image artifact")
    if not pillow_available():
        raise ImageMutationError(
            "Pillow is not installed; install defeat-watermarker[image]"
        )

    from PIL import Image, ImageOps

    try:
        source = Image.open(io.BytesIO(artifact.data))
        source.load()
    except Exception as exc:
        raise ImageMutationError(f"could not decode image: {exc}") from exc

    normalized = ImageOps.exif_transpose(source)
    if normalized.mode in {"RGBA", "LA"} or (
        normalized.mode == "P" and "transparency" in normalized.info
    ):
        rgba = normalized.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        normalized = background
    elif normalized.mode != "RGB":
        normalized = normalized.convert("RGB")
    return normalized


def _encode_jpeg(image, *, quality: int) -> bytes:
    output = io.BytesIO()
    image.save(
        output,
        format="JPEG",
        quality=quality,
        optimize=False,
        progressive=False,
        subsampling=2,
    )
    return output.getvalue()


def _artifact_from_image(source: Artifact, image, *, quality: int) -> Artifact:
    return Artifact(
        data=_encode_jpeg(image, quality=quality),
        media_type="image/jpeg",
        name=source.name,
        modality=Modality.IMAGE,
    )


class JpegReencodeQuality85(ArtifactMutation):
    """Fixed JPEG rendition similar to ordinary platform recompression."""

    mutation_id = "image.jpeg-reencode.q85.v1"

    def apply(self, artifact: Artifact, scenario: MutationScenario) -> Artifact:
        image = _prepare_rgb(artifact)
        try:
            return _artifact_from_image(artifact, image, quality=85)
        finally:
            image.close()


class Resize75Quality85(ArtifactMutation):
    """Resize to 75% in each dimension and emit a deterministic JPEG rendition."""

    mutation_id = "image.resize-75pct.jpeg-q85.v1"

    def apply(self, artifact: Artifact, scenario: MutationScenario) -> Artifact:
        from PIL import Image

        image = _prepare_rgb(artifact)
        try:
            width = max(1, round(image.width * 0.75))
            height = max(1, round(image.height * 0.75))
            resized = image.resize((width, height), Image.Resampling.LANCZOS)
            try:
                return _artifact_from_image(artifact, resized, quality=85)
            finally:
                resized.close()
        finally:
            image.close()


class CenterCrop90Quality85(ArtifactMutation):
    """Center-crop to 90% of the source dimensions and emit JPEG quality 85."""

    mutation_id = "image.center-crop-90pct.jpeg-q85.v1"

    def apply(self, artifact: Artifact, scenario: MutationScenario) -> Artifact:
        image = _prepare_rgb(artifact)
        try:
            width = max(1, round(image.width * 0.90))
            height = max(1, round(image.height * 0.90))
            left = max(0, (image.width - width) // 2)
            top = max(0, (image.height - height) // 2)
            cropped = image.crop((left, top, left + width, top + height))
            try:
                return _artifact_from_image(artifact, cropped, quality=85)
            finally:
                cropped.close()
        finally:
            image.close()
