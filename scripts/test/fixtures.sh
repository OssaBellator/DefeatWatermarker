#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
cd "$DWM_ROOT"
dwm_require_cmd defeat-watermarker-ui
dwm_require_cmd defeat-watermarker
out="$(dwm_tmpdir)"; trap 'rm -rf "$out"' EXIT

defeat-watermarker-ui fixtures/retests/example_text.txt --media-type text/plain \
  --detector-plugin fixture-text --json-output "$out/text-evidence.json"
defeat-watermarker-ui fixtures/retests/example_image.ppm --media-type image/x-portable-pixmap \
  --json-output "$out/image-evidence.json"
defeat-watermarker evidence verify "$out/text-evidence.json"
defeat-watermarker evidence verify "$out/image-evidence.json"
python - "$out" <<'PY'
import json, sys
from pathlib import Path
root=Path(sys.argv[1])
text=json.loads((root/'text-evidence.json').read_text())
image=json.loads((root/'image-evidence.json').read_text())
text_adapter='fixture.text-marker.v1'; hint_adapter='builtin.container-hints.v1'
text_baseline={item['adapter_id']:item for item in text['report']['baseline']}
assert text_baseline[text_adapter]['detected'] is True
text_comparisons=[c for s in text['report']['scenarios'] for c in s['comparisons'] if c['adapter_id']==text_adapter]
assert len(text_comparisons)==3 and all(item['after']['detected'] for item in text_comparisons)
image_baseline={item['adapter_id']:item for item in image['report']['baseline']}
assert image_baseline[hint_adapter]['detected'] is True
image_comparisons=[c for s in image['report']['scenarios'] for c in s['comparisons'] if c['adapter_id']==hint_adapter]
assert image_comparisons and all(not item['after']['detected'] for item in image_comparisons)
assert image['summary']['survival_rate']==0.0
PY
printf 'OK: permanent text/image fixture regressions\n'
