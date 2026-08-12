#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
cd "$DWM_ROOT"

suite="standard"
if [[ "${DWM_TEST_OPTIONAL:-0}" == "1" ]]; then
  suite="optional"
fi

output="${DWM_TEST_REPORT:-$DWM_ROOT/.defeat-watermarker/local-test-report.json}"
exec python scripts/test/recorded.py run --suite "$suite" --output "$output"
