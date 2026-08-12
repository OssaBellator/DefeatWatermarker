#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
cd "$DWM_ROOT"
python scripts/test/check_no_actions.py
python -m pytest -q
python scripts/test/benchmark_regression.py
