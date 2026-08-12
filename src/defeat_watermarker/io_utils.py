from __future__ import annotations

import os
import tempfile
from pathlib import Path

DEFAULT_MAX_ARTIFACT_BYTES = 256 * 1024 * 1024
DEFAULT_MAX_OUTPUT_BYTES = 32 * 1024 * 1024


class BoundedIOError(ValueError):
    """Raised when local file I/O violates explicit size/type bounds."""


def read_bounded_bytes(
    path: Path,
    *,
    max_bytes: int = DEFAULT_MAX_ARTIFACT_BYTES,
) -> bytes:
    if max_bytes < 1:
        raise ValueError("max_bytes must be positive")
    try:
        stat = path.stat()
    except OSError as exc:
        raise BoundedIOError(f"could not stat input file: {exc}") from exc
    if not path.is_file():
        raise BoundedIOError(f"input path is not a regular file: {path}")
    if stat.st_size > max_bytes:
        raise BoundedIOError(f"input file exceeds {max_bytes} bytes")
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise BoundedIOError(f"could not read input file: {exc}") from exc
    # Re-check after reading to cover growth between stat() and read_bytes().
    if len(data) > max_bytes:
        raise BoundedIOError(f"input file exceeds {max_bytes} bytes")
    return data


def atomic_write_text(
    path: Path,
    text: str,
    *,
    max_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
) -> None:
    if max_bytes < 1:
        raise ValueError("max_bytes must be positive")
    encoded = text.encode("utf-8")
    if len(encoded) > max_bytes:
        raise BoundedIOError(f"output exceeds {max_bytes} bytes")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, path)
        except Exception:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
            raise
    except OSError as exc:
        raise BoundedIOError(f"could not write output file atomically: {exc}") from exc
