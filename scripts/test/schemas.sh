#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
cd "$DWM_ROOT"
python scripts/test/schema_audit.py
printf 'OK: published schema audit\n'
