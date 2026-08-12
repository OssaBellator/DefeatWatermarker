from __future__ import annotations

import io
import math
import sys
import wave
from array import array
from dataclasses import dataclass

from ..models import Artifact, Modality, MutationScenario
from .base import ArtifactMutation

_MAX_PCM_FRAMES = 2_000_000
_MAX_CHANNELS = 8
_TARGET_RATE = 16_000


class AudioMutationError(ValueError):
    """Raised when a fixed PCM-WAV workflow transformation cannot be applied."""


@dataclass(slots=True)
class _Pcm16:
    rate: int
    channels: int
    samples: array

    @property
    def frames(self) -> int:
        return len(self.samples) // self.channels


def _decode_pcm16(artifact: Artifact) -> _Pcm16:
    if artifact.modality not in {Modality.AUDIO, Modality.UNKNOWN}:
        raise AudioMutationError("audio mutation requires an audio artifact")
    try:
        with wave.open(io.BytesIO(artifact.data), "rb") as reader:
            if reader.getcomptype() != "NONE":
                raise AudioMutationError("audio suite supports uncompressed PCM WAV only")
            if reader.getsampwidth() != 2:
                raise AudioMutationError("audio suite supports 16-bit PCM WAV only")
            channels = reader.getnchannels()
            rate = reader.getframerate()
            frames = reader.getnframes()
            if not 1 <= channels <= _MAX_CHANNELS:
                raise AudioMutationError(f"WAV channel count must be in 1..{_MAX_CHANNELS}")
            if not 1 <= rate <= 384_000:
                raise AudioMutationError("WAV sample rate is outside the supported bound")
            if frames > _MAX_PCM_FRAMES:
                raise AudioMutationError(f"WAV exceeds {_MAX_PCM_FRAMES} PCM frames")
            raw = reader.readframes(frames)
    except wave.Error as exc:
        raise AudioMutationError(f"could not decode WAV: {exc}") from exc

    expected = frames * channels * 2
    if len(raw) != expected:
        raise AudioMutationError("WAV PCM payload is truncated or inconsistent")
    samples = array("h")
    samples.frombytes(raw)
    if sys.byteorder != "little":
        samples.byteswap()
    return _Pcm16(rate=rate, channels=channels, samples=samples)


def _encode_pcm16(source: Artifact, pcm: _Pcm16) -> Artifact:
    output = io.BytesIO()
    encoded = array("h", pcm.samples)
    if sys.byteorder != "little":
        encoded.byteswap()
    with wave.open(output, "wb") as writer:
        writer.setnchannels(pcm.channels)
        writer.setsampwidth(2)
        writer.setframerate(pcm.rate)
        writer.writeframes(encoded.tobytes())
    return Artifact(
        data=output.getvalue(),
        media_type="audio/wav",
        name=source.name,
        modality=Modality.AUDIO,
    )


def _clamp_pcm16(value: int) -> int:
    return min(32767, max(-32768, value))


class WavPcm16GainMinus3Db(ArtifactMutation):
    """Apply a fixed -3 dB gain and rewrite as 16-bit PCM WAV."""

    mutation_id = "audio.wav-pcm16.gain-minus3db.v1"

    def apply(self, artifact: Artifact, scenario: MutationScenario) -> Artifact:
        pcm = _decode_pcm16(artifact)
        factor = math.pow(10.0, -3.0 / 20.0)
        adjusted = array("h", (_clamp_pcm16(round(sample * factor)) for sample in pcm.samples))
        return _encode_pcm16(
            artifact, _Pcm16(rate=pcm.rate, channels=pcm.channels, samples=adjusted)
        )


class WavPcm16DownmixMono(ArtifactMutation):
    """Downmix PCM channels to mono by arithmetic mean."""

    mutation_id = "audio.wav-pcm16.downmix-mono.v1"

    def apply(self, artifact: Artifact, scenario: MutationScenario) -> Artifact:
        pcm = _decode_pcm16(artifact)
        if pcm.channels == 1:
            mono = array("h", pcm.samples)
        else:
            values = array("h")
            for frame in range(pcm.frames):
                offset = frame * pcm.channels
                total = sum(pcm.samples[offset + channel] for channel in range(pcm.channels))
                values.append(_clamp_pcm16(round(total / pcm.channels)))
            mono = values
        return _encode_pcm16(artifact, _Pcm16(rate=pcm.rate, channels=1, samples=mono))


class WavPcm16Resample16Khz(ArtifactMutation):
    """Linearly resample PCM audio to a fixed 16 kHz workflow rendition."""

    mutation_id = "audio.wav-pcm16.resample-16khz.v1"

    def apply(self, artifact: Artifact, scenario: MutationScenario) -> Artifact:
        pcm = _decode_pcm16(artifact)
        if pcm.rate == _TARGET_RATE:
            return _encode_pcm16(artifact, pcm)
        if pcm.frames == 0:
            return _encode_pcm16(
                artifact,
                _Pcm16(rate=_TARGET_RATE, channels=pcm.channels, samples=array("h")),
            )
        out_frames = max(1, round(pcm.frames * _TARGET_RATE / pcm.rate))
        if out_frames > _MAX_PCM_FRAMES:
            raise AudioMutationError(
                f"resampled WAV would exceed {_MAX_PCM_FRAMES} PCM frames"
            )
        output = array("h")
        step = pcm.rate / _TARGET_RATE
        for frame in range(out_frames):
            source_position = frame * step
            left = min(int(source_position), pcm.frames - 1)
            right = min(left + 1, pcm.frames - 1)
            fraction = source_position - left
            for channel in range(pcm.channels):
                a = pcm.samples[left * pcm.channels + channel]
                b = pcm.samples[right * pcm.channels + channel]
                value = round(a + (b - a) * fraction)
                output.append(_clamp_pcm16(value))
        return _encode_pcm16(
            artifact,
            _Pcm16(rate=_TARGET_RATE, channels=pcm.channels, samples=output),
        )
