#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
cd "$DWM_ROOT"
for command in \
  defeat-watermarker \
  defeat-watermarker-attack \
  defeat-watermarker-ui \
  defeat-watermarker-scan-verify \
  defeat-watermarker-batch \
  defeat-watermarker-batch-verify \
  defeat-watermarker-benchmark-verify \
  defeat-watermarker-benchmark-baseline \
  defeat-watermarker-detector-conformance \
  defeat-watermarker-report; do
  dwm_require_cmd "$command"
  "$command" --help >/dev/null
done
printf 'OK: installed CLI entry points respond to --help\n'
