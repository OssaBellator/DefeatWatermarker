#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
cd "$DWM_ROOT"
dwm_require_cmd defeat-watermarker
dwm_require_cmd defeat-watermarker-benchmark-verify
dwm_require_cmd defeat-watermarker-benchmark-baseline
dwm_require_cmd defeat-watermarker-report
out="$(dwm_tmpdir)"; trap 'rm -rf "$out"' EXIT

defeat-watermarker benchmark reliability fixtures/benchmarks/text-detectors/reliability-v0.1.json \
  --detector-plugin fixture-text --output "$out/reliability.json"
defeat-watermarker benchmark interoperability fixtures/benchmarks/text-detectors/interoperability-v0.1.json \
  --detector-plugin fixture-text --detector-plugin fixture-text-secondary --output "$out/interoperability.json"
defeat-watermarker-benchmark-verify "$out/reliability.json"
defeat-watermarker-benchmark-verify "$out/interoperability.json"
defeat-watermarker-benchmark-baseline create "$out/reliability.json" --output "$out/baseline.json"
defeat-watermarker-benchmark-baseline compare "$out/reliability.json" --baseline "$out/baseline.json" --output "$out/comparison.json"
defeat-watermarker-benchmark-baseline verify-comparison "$out/comparison.json"
defeat-watermarker-report "$out/reliability.json" --output "$out/reliability.html"
defeat-watermarker-report "$out/interoperability.json" --output "$out/interoperability.html"
python - "$out" <<'PY'
import json, sys
from pathlib import Path
root=Path(sys.argv[1])
r=json.loads((root/'reliability.json').read_text())
i=json.loads((root/'interoperability.json').read_text())
c=json.loads((root/'comparison.json').read_text())
assert r['summary']['true_positive']==1 and r['summary']['true_negative']==1
assert r['summary']['false_positive']==0 and r['summary']['false_negative']==0
pair=i['pairs'][0]
assert pair['comparable_cases']==3 and pair['detection_agreements']==2 and pair['detection_disagreements']==1
assert c['status']=='same_or_better' and len(c['comparison_id'])==64
for name in ('reliability.html','interoperability.html'):
    html=(root/name).read_text(encoding='utf-8')
    assert '<script' not in html and 'http://' not in html and 'https://' not in html
PY
printf 'OK: provider benchmark, baseline, comparison and report chain\n'
