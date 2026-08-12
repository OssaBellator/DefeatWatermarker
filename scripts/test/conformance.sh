#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
cd "$DWM_ROOT"
dwm_require_cmd defeat-watermarker-detector-conformance
dwm_require_cmd defeat-watermarker-report
out="$(dwm_tmpdir)"; trap 'rm -rf "$out"' EXIT

defeat-watermarker-detector-conformance run \
  fixtures/retests/example_text.txt \
  --media-type text/plain \
  --detector-plugin fixture-text \
  --output "$out/conformance.json"

defeat-watermarker-detector-conformance verify "$out/conformance.json"
defeat-watermarker-report "$out/conformance.json" --output "$out/conformance.html"

python - "$out/conformance.json" "$out/conformance.html" <<'PY'
import json, sys
from pathlib import Path
payload=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
rendered=Path(sys.argv[2]).read_text(encoding='utf-8')
assert payload['passed'] is True
assert payload['adapter_id'] == 'fixture.text-marker.v1'
assert len(payload['report_id']) == 64
required={
    'runtime_identity',
    'runtime_identity_stable',
    'read_only_capability',
    'capabilities_deterministic',
    'supports_artifact',
    'supports_deterministic',
    'adapter_id_match',
    'family_match',
    'deterministic_detection',
    'source_unchanged',
}
assert required.issubset(payload['checks'])
assert 'adapter-runtime=profile=fixture-primary-v1' in payload['runtime_identity']
assert 'adapter-runtime=marker-version=1' in payload['runtime_identity']
assert 'DefeatWatermarker detector conformance report' in rendered
assert '<script' not in rendered
assert 'http://' not in rendered and 'https://' not in rendered
PY
printf 'OK: explicit provider detector conformance, verification and static report\n'
