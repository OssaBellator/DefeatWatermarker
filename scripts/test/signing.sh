#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
cd "$DWM_ROOT"
python - <<'PY'
import importlib.util
if importlib.util.find_spec('cryptography') is None:
    raise SystemExit('cryptography is required; install defeat-watermarker[signing]')
PY
python -m pytest -q tests/test_signatures.py tests/test_evidence_signature_cli.py
