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

python -m venv "$out/venv"
"$out/venv/bin/python" -m pip install --no-deps "$wheel"

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

printf 'OK: offline wheel builds, installs cleanly and exposes all public CLIs\n'
