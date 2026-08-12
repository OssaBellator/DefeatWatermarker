# Local test runners

GitHub Actions is intentionally disabled on the current feature branch while hosted-runner quota is unavailable. These scripts are the executable source of truth for the checks that previously lived in workflow YAML.

## Setup

Create a Python 3.11+ virtual environment, then install the project and the synthetic provider detector fixture:

```bash
python -m pip install -e '.[dev,signing,c2pa,image]' -e fixtures/plugins/example_text_detector
```

No test script installs packages or accesses the network. Dependencies must already be present.

## Fast local run

```bash
bash scripts/test/core.sh
bash scripts/test/cli_smoke.sh
bash scripts/test/benchmarks.sh
bash scripts/test/batch.sh
bash scripts/test/fixtures.sh
```

`core.sh` runs pytest, checks that Actions workflow files have not been reintroduced, and runs the standalone semantic benchmark regression smoke test.

For all heavyweight/optional media tests too:

```bash
DWM_TEST_OPTIONAL=1 bash scripts/test/all.sh
```

Optional tests require `cryptography`, `c2pa-python`, Pillow, OpenSSL, and FFmpeg as applicable.

The scripts use temporary directories, do not export transformed media chosen for failed attribution, and retain the project's detector-blind fixed-suite boundary.
