from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Protocol

from ..io_utils import DEFAULT_MAX_ARTIFACT_BYTES
from ..models import Artifact, Modality, MutationScenario
from .base import ArtifactMutation

_FFMPEG_TIMEOUT_SECONDS = 60.0
_MAX_ERROR_BYTES = 8192


class VideoMutationError(ValueError):
    """Raised when a fixed video rendition cannot be completed safely."""


class VideoExecutor(Protocol):
    def transcode(self, data: bytes, *, video_filter: str | None) -> bytes: ...

    def runtime_identity(self) -> tuple[str, ...]: ...


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


class FfmpegExecutor:
    """Bounded no-shell FFmpeg runner for predefined rendition commands."""

    def __init__(
        self,
        *,
        timeout_seconds: float = _FFMPEG_TIMEOUT_SECONDS,
        max_output_bytes: int = DEFAULT_MAX_ARTIFACT_BYTES,
    ) -> None:
        if not 0 < timeout_seconds <= 300:
            raise ValueError("FFmpeg timeout must be in (0, 300] seconds")
        if max_output_bytes < 1:
            raise ValueError("max_output_bytes must be positive")
        self.timeout_seconds = timeout_seconds
        self.max_output_bytes = max_output_bytes

    def _binary(self) -> str:
        binary = shutil.which("ffmpeg")
        if binary is None:
            raise VideoMutationError("ffmpeg is not installed or not on PATH")
        return binary

    def runtime_identity(self) -> tuple[str, ...]:
        binary = self._binary()
        try:
            completed = subprocess.run(
                [binary, "-version"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise VideoMutationError(f"could not identify ffmpeg runtime: {exc}") from exc
        first_line = completed.stdout.decode("utf-8", errors="replace").splitlines()[:1]
        identity = first_line[0][:400] if first_line else "ffmpeg=unknown"
        return (identity,)

    def transcode(self, data: bytes, *, video_filter: str | None) -> bytes:
        if len(data) > DEFAULT_MAX_ARTIFACT_BYTES:
            raise VideoMutationError(
                f"video input exceeds {DEFAULT_MAX_ARTIFACT_BYTES} bytes"
            )
        binary = self._binary()
        with tempfile.TemporaryDirectory(prefix="defeat-watermarker-video-") as directory:
            root = Path(directory)
            output = root / "rendition.mp4"
            errors = root / "ffmpeg.stderr"
            command = [
                binary,
                "-hide_banner",
                "-loglevel",
                "error",
                "-xerror",
                "-nostdin",
                "-y",
                "-i",
                "pipe:0",
                "-map",
                "0:v:0",
                "-map",
                "0:a?",
            ]
            if video_filter is not None:
                command.extend(["-vf", video_filter])
            command.extend(
                [
                    "-c:v",
                    "libx264",
                    "-preset",
                    "medium",
                    "-crf",
                    "23",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "128k",
                    "-movflags",
                    "+faststart",
                    str(output),
                ]
            )
            try:
                with errors.open("wb") as error_stream:
                    completed = subprocess.run(
                        command,
                        input=data,
                        stdout=subprocess.DEVNULL,
                        stderr=error_stream,
                        timeout=self.timeout_seconds,
                        check=False,
                    )
            except subprocess.TimeoutExpired as exc:
                raise VideoMutationError(
                    f"ffmpeg exceeded {self.timeout_seconds:g} second timeout"
                ) from exc
            except OSError as exc:
                raise VideoMutationError(f"could not execute ffmpeg: {exc}") from exc

            if completed.returncode != 0:
                try:
                    with errors.open("rb") as stream:
                        detail = stream.read(_MAX_ERROR_BYTES).decode("utf-8", errors="replace")
                except OSError:
                    detail = ""
                detail = detail.strip().replace("\n", " ")[:2000]
                raise VideoMutationError(
                    f"ffmpeg rendition failed with code {completed.returncode}"
                    + (f": {detail}" if detail else "")
                )
            if not output.is_file():
                raise VideoMutationError("ffmpeg did not create a rendition")
            size = output.stat().st_size
            if size > self.max_output_bytes:
                raise VideoMutationError(
                    f"ffmpeg output exceeds {self.max_output_bytes} bytes"
                )
            return output.read_bytes()


class _FfmpegMutation(ArtifactMutation):
    video_filter: str | None = None

    def __init__(self, executor: VideoExecutor | None = None) -> None:
        self.executor = executor or FfmpegExecutor()

    def apply(self, artifact: Artifact, scenario: MutationScenario) -> Artifact:
        if artifact.modality not in {Modality.VIDEO, Modality.UNKNOWN}:
            raise VideoMutationError("video mutation requires a video artifact")
        rendered = self.executor.transcode(artifact.data, video_filter=self.video_filter)
        return Artifact(
            data=rendered,
            media_type="video/mp4",
            name=artifact.name,
            modality=Modality.VIDEO,
        )

    def runtime_identity(self) -> tuple[str, ...]:
        return self.executor.runtime_identity()


class FfmpegH264Crf23(_FfmpegMutation):
    """Fixed H.264 CRF 23 / AAC rendition at source dimensions."""

    mutation_id = "video.ffmpeg-h264-crf23-aac128.v1"


class FfmpegScale75H264Crf23(_FfmpegMutation):
    """Fixed approximately-75% even-dimension scale followed by H.264/AAC rendition."""

    mutation_id = "video.ffmpeg-scale75-h264-crf23-aac128.v1"
    video_filter = "scale=trunc(iw*3/8)*2:trunc(ih*3/8)*2"
