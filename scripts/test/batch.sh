#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
cd "$DWM_ROOT"
dwm_require_cmd defeat-watermarker-batch
dwm_require_cmd defeat-watermarker-batch-verify
dwm_require_cmd defeat-watermarker-report
out="$(dwm_tmpdir)"; trap 'rm -rf "$out"' EXIT

defeat-watermarker-batch fixtures/retests --scan-only --output-dir "$out/scan"
defeat-watermarker-batch-verify "$out/scan"
defeat-watermarker-batch fixtures/retests --detector-plugin fixture-text --output-dir "$out/attack"
defeat-watermarker-batch-verify "$out/attack"
defeat-watermarker-report "$out/attack" --output "$out/report.html"
python - "$out" <<'PY'
import json, sys
from pathlib import Path
root=Path(sys.argv[1])
scan=json.loads((root/'scan'/'batch.json').read_text())
attack=json.loads((root/'attack'/'batch.json').read_text())
assert len(scan['records']) >= 4 and all(item['mode']=='scan' for item in scan['records'])
modes={item['relative_path']:item['mode'] for item in attack['records']}
assert modes['example_image.ppm']=='attack'
assert modes['example_text.txt']=='attack'
assert modes['example_unknown.bin']=='scan'
html=(root/'report.html').read_text(encoding='utf-8')
assert '<script' not in html and 'http://' not in html and 'https://' not in html
PY
printf 'OK: batch scan/attack evidence and static report\n'
