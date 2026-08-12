# Local test runners

GitHub Actions is intentionally disabled on the current feature branch while hosted-runner quota is unavailable. These scripts are the executable source of truth for validation that previously lived in workflow YAML.

## Setup

Create a Python 3.11+ virtual environment, then install the project and the synthetic provider detector fixture:

```bash
python -m pip install -e '.[dev,signing,c2pa,image]' -e fixtures/plugins/example_text_detector
```

No test script installs packages or accesses the network. Dependencies must already be present.

## Standard recorded run

```bash
bash scripts/test/all.sh
```

`all.sh` runs the standard suite through `scripts/test/recorded.py` and writes a content-addressed result to:

```text
.defeat-watermarker/local-test-report.json
```

Override that destination with `DWM_TEST_REPORT=/path/report.json`.

Verify a saved run independently:

```bash
python scripts/test/recorded.py verify .defeat-watermarker/local-test-report.json
```

The record binds the selected suite, current Git commit when available, Python runtime and every attempted command/return code. `passed` is recomputed from the recorded steps; a rehashed truncated suite or rehashed report that hides a failed command is rejected.

## Fast/component runs

```bash
bash scripts/test/preflight.sh
bash scripts/test/core.sh
bash scripts/test/cli_smoke.sh
bash scripts/test/conformance.sh
bash scripts/test/benchmarks.sh
bash scripts/test/batch.sh
bash scripts/test/fixtures.sh
```

`preflight.sh` rejects reintroduced Actions workflow files, verifies Python/package metadata and public CLI declarations, then byte-compiles the source tree.

`core.sh` runs preflight, pytest and the standalone semantic benchmark regression smoke test.

`conformance.sh` explicitly loads the fixture detector entry point, verifies the read-only/deterministic plugin contract, verifies the content-addressed conformance JSON and renders a static local HTML report.

## Optional heavyweight suite

Include signing, FFmpeg/video and real C2PA checks:

```bash
DWM_TEST_OPTIONAL=1 bash scripts/test/all.sh
```

Equivalent explicit recorded invocation:

```bash
python scripts/test/recorded.py run \
  --suite optional \
  --output .defeat-watermarker/local-test-report.json
```

Optional tests require `cryptography`, `c2pa-python`, Pillow, OpenSSL and FFmpeg as applicable.

## Recorded suite names

- `core`: preflight + pytest + semantic benchmark smoke;
- `standard`: core plus CLI smoke, detector conformance, provider benchmarks, batch and permanent fixtures;
- `optional`: standard plus signing, video and real signed/tampered C2PA tests.

The scripts use temporary directories, do not export transformed media chosen for failed attribution, and retain the project's detector-blind fixed-suite boundary.
