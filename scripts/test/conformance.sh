#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
cd "$DWM_ROOT"
dwm_require_cmd defeat-watermarker-detector-conformance
out="$(dwm_tmpdir)"; trap 'rm -rf "$out"' EXIT

defeat-watermarker-detector-conformance run \
  fixtures/retests/example_text.txt \
  --media-type text/plain \
  --detector-plugin fixture-text \
  --output "$out/conformance.json"

defeat-watermarker-detector-conformance verify "$out/conformance.json"

python - "$out/conformance.json" <<'PY'
import json, sys
from pathlib import Path
payload=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
assert payload['passed'] is True
assert payload['adapter_id'] == 'fixture.text-marker.v1'
assert len(payload['report_id']) == 64
required={
    'runtime_identity',
    'read_only_capability',
    'supports_artifact',
    'adapter_id_match',
    'family_match',
    'deterministic_detection',
    'source_unchanged',
}
assert required.issubset(payload['checks'])
assert 'adapter-runtime=profile=fixture-primary-v1' in payload['runtime_identity']
assert 'adapter-runtime=marker-version=1' in payload['runtime_identity']
PY
printf 'OK: explicit provider detector conformance and evidence verification\n'
