#!/usr/bin/env bash
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
cd "$DWM_ROOT"

out="$(dwm_tmpdir)"; trap 'rm -rf "$out"' EXIT

python -m pip wheel \
  --no-deps \
  --no-build-isolation \
  . \
  -w "$out/wheels"

wheel="$(find "$out/wheels" -maxdepth 1 -type f -name 'defeat_watermarker-*.whl' -print -quit)"
if [[ -z "$wheel" ]]; then
  echo 'defeat-watermarker wheel was not produced' >&2
  exit 1
fi

python - "$wheel" <<'PY'
from pathlib import Path
import sys
from zipfile import ZipFile

wheel = Path(sys.argv[1])
forbidden_prefixes = ('tests/', 'fixtures/', 'scripts/', '.github/')
private_markers = (
    b'-----BEGIN PRIVATE KEY-----',
    b'-----BEGIN EC PRIVATE KEY-----',
    b'-----BEGIN RSA PRIVATE KEY-----',
    b'-----BEGIN OPENSSH PRIVATE KEY-----',
)
with ZipFile(wheel) as archive:
    names = archive.namelist()
    assert names, 'wheel is empty'
    assert any(name.startswith('defeat_watermarker/') for name in names)
    leaked = [
        name
        for name in names
        if name.startswith(forbidden_prefixes)
        or '/tests/' in name
        or '/fixtures/' in name
        or '/scripts/' in name
    ]
    assert not leaked, f'non-runtime repository content leaked into wheel: {leaked[:10]}'
    for info in archive.infolist():
        if info.is_dir() or info.file_size > 4 * 1024 * 1024:
            continue
        data = archive.read(info)
        for marker in private_markers:
            assert marker not in data, f'private-key marker found in wheel member: {info.filename}'
PY

python -m venv "$out/venv"
"$out/venv/bin/python" -m pip install --no-deps "$wheel"
"$out/venv/bin/python" -m pip check

commands=(
  defeat-watermarker
  defeat-watermarker-attack
  defeat-watermarker-ui
  defeat-watermarker-scan-verify
  defeat-watermarker-batch
  defeat-watermarker-batch-verify
  defeat-watermarker-benchmark-verify
  defeat-watermarker-benchmark-baseline
  defeat-watermarker-detector-conformance
  defeat-watermarker-regression
  defeat-watermarker-signature
  defeat-watermarker-report
)

for command in "${commands[@]}"; do
  "$out/venv/bin/$command" --help >/dev/null
done

"$out/venv/bin/python" - <<'PY'
import importlib.metadata as metadata

expected = {
    'defeat-watermarker',
    'defeat-watermarker-attack',
    'defeat-watermarker-ui',
    'defeat-watermarker-scan-verify',
    'defeat-watermarker-batch',
    'defeat-watermarker-batch-verify',
    'defeat-watermarker-benchmark-verify',
    'defeat-watermarker-benchmark-baseline',
    'defeat-watermarker-detector-conformance',
    'defeat-watermarker-regression',
    'defeat-watermarker-signature',
    'defeat-watermarker-report',
}
installed = {
    entry.name
    for entry in metadata.entry_points().select(group='console_scripts')
    if entry.dist is not None
    and entry.dist.metadata.get('Name') == 'defeat-watermarker'
}
assert installed == expected, (installed, expected)
PY

printf 'OK: offline wheel builds, passes pip check, contains runtime-only content and exposes all public CLIs\n'
