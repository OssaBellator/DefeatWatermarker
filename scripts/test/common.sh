#!/usr/bin/env bash
set -euo pipefail
DWM_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export DWM_ROOT
export PYTHONPATH="$DWM_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

dwm_require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "missing required command: $1" >&2; return 127; }
}

dwm_tmpdir() {
  mktemp -d "${TMPDIR:-/tmp}/defeat-watermarker-test.XXXXXX"
}
