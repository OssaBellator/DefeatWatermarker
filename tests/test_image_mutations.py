import io

from PIL import Image

from defeat_watermarker.models import Artifact, Modality, MutationScenario
from defeat_watermarker.mutations.image import (
    CenterCrop90Quality85,
    JpegReencodeQuality85,
    Resize75Quality85,
)


def _png_artifact(width: int = 100, height: int = 80) -> Artifact:
    image = Image.new("RGB", (width, height), (120, 80, 40))
    output = io.BytesIO()
    image.save(output, format="PNG")
    image.close()
    return Artifact(
        data=output.getvalue(),
        media_type="image/png",
        name="fixture.png",
        modality=Modality.IMAGE,
    )


def _scenario(mutation_id: str) -> MutationScenario:
    return MutationScenario(
        scenario_id="fixture",
        mutation_id=mutation_id,
        modality=Modality.IMAGE,
        transformation_family="fixture",
    )


def _size(artifact: Artifact) -> tuple[int, int]:
    with Image.open(io.BytesIO(artifact.data)) as image:
        return image.size


def test_reencode_outputs_jpeg_without_export_surface() -> None:
    source = _png_artifact()
    result = JpegReencodeQuality85().apply(
        source, _scenario(JpegReencodeQuality85.mutation_id)
    )
    assert result.media_type == "image/jpeg"
    assert result.modality is Modality.IMAGE
    assert _size(result) == (100, 80)
    assert result.data != source.data


def test_resize_is_fixed_75_percent() -> None:
    result = Resize75Quality85().apply(
        _png_artifact(), _scenario(Resize75Quality85.mutation_id)
    )
    assert _size(result) == (75, 60)


def test_crop_is_fixed_90_percent() -> None:
    result = CenterCrop90Quality85().apply(
        _png_artifact(), _scenario(CenterCrop90Quality85.mutation_id)
    )
    assert _size(result) == (90, 72)
