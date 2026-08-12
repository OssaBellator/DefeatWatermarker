#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
cd "$DWM_ROOT"
bash scripts/test/preflight.sh
python -m pytest -q
python scripts/test/benchmark_regression.py
