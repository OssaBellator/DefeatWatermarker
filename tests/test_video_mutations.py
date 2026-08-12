from defeat_watermarker.models import Artifact, Modality, MutationScenario
from defeat_watermarker.mutations.video import FfmpegH264Crf23, FfmpegScale75H264Crf23


class FakeExecutor:
    def __init__(self) -> None:
        self.filters: list[str | None] = []

    def transcode(self, data: bytes, *, video_filter: str | None) -> bytes:
        self.filters.append(video_filter)
        return b"fixed-video-rendition"

    def runtime_identity(self) -> tuple[str, ...]:
        return ("ffmpeg fixture",)


def _scenario(mutation_id: str) -> MutationScenario:
    return MutationScenario(
        scenario_id="fixture",
        mutation_id=mutation_id,
        modality=Modality.VIDEO,
        transformation_family="fixture",
    )


def test_fixed_video_transcode_has_no_detector_input_or_user_command_surface() -> None:
    executor = FakeExecutor()
    mutation = FfmpegH264Crf23(executor=executor)
    result = mutation.apply(
        Artifact(data=b"source", media_type="video/mp4", modality=Modality.VIDEO),
        _scenario(mutation.mutation_id),
    )
    assert result.data == b"fixed-video-rendition"
    assert result.media_type == "video/mp4"
    assert executor.filters == [None]
    assert mutation.runtime_identity() == ("ffmpeg fixture",)


def test_scale_filter_is_fixed_in_implementation() -> None:
    executor = FakeExecutor()
    mutation = FfmpegScale75H264Crf23(executor=executor)
    mutation.apply(
        Artifact(data=b"source", media_type="video/mp4", modality=Modality.VIDEO),
        _scenario(mutation.mutation_id),
    )
    assert executor.filters == ["scale=trunc(iw*3/8)*2:trunc(ih*3/8)*2"]
