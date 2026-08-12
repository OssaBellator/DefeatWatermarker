#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
cd "$DWM_ROOT"
dwm_require_cmd openssl
dwm_require_cmd defeat-watermarker-ui
dwm_require_cmd defeat-watermarker
python - <<'PY'
from defeat_watermarker.adapters.c2pa import C2paPythonBackend
if not C2paPythonBackend.available():
    raise SystemExit('c2pa-python is required; install defeat-watermarker[c2pa,image]')
PY
out="$(dwm_tmpdir)"; trap 'rm -rf "$out"' EXIT
openssl ecparam -name prime256v1 -genkey -noout -out "$out/root.key"
openssl req -new -x509 -sha256 -days 3650 -key "$out/root.key" \
  -subj '/O=DefeatWatermarker Test Fixtures/CN=Ephemeral C2PA Root' \
  -config fixtures/c2pa/openssl-fixture.cnf -extensions root_ext -out "$out/root.pem"
openssl ecparam -name prime256v1 -genkey -noout -out "$out/leaf-sec1.key"
openssl pkcs8 -topk8 -nocrypt -in "$out/leaf-sec1.key" -out "$out/leaf.key"
openssl req -new -sha256 -key "$out/leaf.key" \
  -subj '/O=DefeatWatermarker Test Fixtures/CN=Ephemeral C2PA Signer' -out "$out/leaf.csr"
openssl x509 -req -sha256 -days 365 -in "$out/leaf.csr" -CA "$out/root.pem" -CAkey "$out/root.key" \
  -CAcreateserial -extfile fixtures/c2pa/openssl-fixture.cnf -extensions leaf_ext -out "$out/leaf.pem"
cat "$out/leaf.pem" "$out/root.pem" > "$out/chain.pem"
python scripts/generate_c2pa_retest_fixture.py --source fixtures/retests/example_image.ppm \
  --chain "$out/chain.pem" --private-key "$out/leaf.key" --jpeg-source "$out/source.jpg" \
  --signed "$out/signed.jpg" --tampered "$out/tampered.jpg" --metadata "$out/generation.json"
defeat-watermarker-ui "$out/signed.jpg" --media-type image/jpeg --c2pa-trust-anchors "$out/root.pem" \
  --json-output "$out/signed-evidence.json"
defeat-watermarker evidence verify "$out/signed-evidence.json"
defeat-watermarker scan "$out/tampered.jpg" --media-type image/jpeg --c2pa-trust-anchors "$out/root.pem" \
  --output "$out/tampered-scan.json"
python - "$out" <<'PY'
import json, sys
from pathlib import Path
root=Path(sys.argv[1]); adapter='c2pa.reader.v1'
signed=json.loads((root/'signed-evidence.json').read_text()); tampered=json.loads((root/'tampered-scan.json').read_text())
s={item['adapter_id']:item for item in signed['report']['baseline']}[adapter]
t={item['adapter_id']:item for item in tampered['results']}[adapter]
assert s['detected'] and s['cryptographically_verified'] and s['verification_state'] in {'valid','trusted'}
assert t['detected'] and not t['cryptographically_verified'] and t['verification_state']=='invalid'
PY
printf 'OK: real signed/tampered C2PA regression\n'
