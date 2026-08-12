#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
cd "$DWM_ROOT"
bash scripts/test/core.sh
bash scripts/test/cli_smoke.sh
bash scripts/test/benchmarks.sh
bash scripts/test/batch.sh
bash scripts/test/fixtures.sh
if [[ "${DWM_TEST_OPTIONAL:-0}" == "1" ]]; then
  bash scripts/test/signing.sh
  bash scripts/test/video.sh
  bash scripts/test/c2pa.sh
else
  echo 'Optional signing/video/C2PA tests skipped; run with DWM_TEST_OPTIONAL=1 to include them.'
fi
