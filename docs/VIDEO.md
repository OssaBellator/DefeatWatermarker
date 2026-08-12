# Fixed video rendition suite

The video suite uses FFmpeg as an optional system dependency. It is intentionally a small fixed workflow surface rather than a generic media-command interface.

Current mutations:

- H.264 `libx264`, CRF 23, medium preset, `yuv420p`, optional audio re-encoded as AAC 128 kbit/s;
- the same rendition after a fixed approximately-75% even-dimension scale.

FFmpeg is invoked as an argument vector with `shell=False` semantics through `subprocess.run`. Input arrives over stdin. The output is written only to a private temporary directory, is byte-bounded before it is read back into the in-memory evaluation pipeline, and is deleted with the temporary directory. Execution has a fixed timeout and `-xerror` is enabled.

The command does not expose arbitrary user codec/filter arguments and does not receive detector scores or results.

Evaluation evidence records the SHA-256 and byte length of the private derivative plus the FFmpeg runtime identity. It still does not export derivative bytes.

`python -m defeat_watermarker capabilities` reports whether `ffmpeg` is currently available on `PATH`. Profile assessment counts a video scenario only when its mutation implementation is runnable in the current environment.
