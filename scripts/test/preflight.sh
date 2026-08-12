#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
cd "$DWM_ROOT"
python scripts/test/check_no_actions.py
python scripts/test/preflight.py
python -m compileall -q src/defeat_watermarker
printf 'OK: source tree compiles locally\n'
