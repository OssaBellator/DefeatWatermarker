import io
import wave
from array import array

from defeat_watermarker.models import Artifact, Modality, MutationScenario
from defeat_watermarker.mutations.audio import (
    WavPcm16DownmixMono,
    WavPcm16GainMinus3Db,
    WavPcm16Resample16Khz,
)


def _wav_artifact(*, channels: int = 2, rate: int = 8000, frames: int = 100) -> Artifact:
    samples = array("h")
    for frame in range(frames):
        for channel in range(channels):
            samples.append((frame * 100 + channel * 1000) % 20_000 - 10_000)
    output = io.BytesIO()
    with wave.open(output, "wb") as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(2)
        writer.setframerate(rate)
        writer.writeframes(samples.tobytes())
    return Artifact(
        data=output.getvalue(),
        media_type="audio/wav",
        modality=Modality.AUDIO,
    )


def _scenario(mutation_id: str) -> MutationScenario:
    return MutationScenario(
        scenario_id="fixture",
        mutation_id=mutation_id,
        modality=Modality.AUDIO,
        transformation_family="fixture",
    )


def _params(artifact: Artifact) -> tuple[int, int, int]:
    with wave.open(io.BytesIO(artifact.data), "rb") as reader:
        return reader.getnchannels(), reader.getframerate(), reader.getnframes()


def test_gain_rewrites_pcm_with_same_shape() -> None:
    source = _wav_artifact()
    result = WavPcm16GainMinus3Db().apply(
        source, _scenario(WavPcm16GainMinus3Db.mutation_id)
    )
    assert _params(result) == (2, 8000, 100)
    assert result.data != source.data


def test_downmix_produces_mono() -> None:
    result = WavPcm16DownmixMono().apply(
        _wav_artifact(), _scenario(WavPcm16DownmixMono.mutation_id)
    )
    assert _params(result) == (1, 8000, 100)


def test_resample_produces_16khz_and_expected_frame_count() -> None:
    result = WavPcm16Resample16Khz().apply(
        _wav_artifact(rate=8000, frames=100),
        _scenario(WavPcm16Resample16Khz.mutation_id),
    )
    assert _params(result) == (2, 16000, 200)
