#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
cd "$DWM_ROOT"
dwm_require_cmd ffmpeg
dwm_require_cmd defeat-watermarker-attack
out="$(dwm_tmpdir)"; trap 'rm -rf "$out"' EXIT
ffmpeg -hide_banner -loglevel error -f lavfi -i testsrc=size=64x64:rate=2 -t 1 -c:v libx264 -pix_fmt yuv420p "$out/source.mp4"
defeat-watermarker-attack "$out/source.mp4" --media-type video/mp4 --suite suites/video-platform-v0.1.json --output "$out/video-evidence.json"
python -m defeat_watermarker evidence verify "$out/video-evidence.json" --suite suites/video-platform-v0.1.json
printf 'OK: FFmpeg video robustness smoke test\n'
