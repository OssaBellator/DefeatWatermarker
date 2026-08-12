# DefeatWatermarker

DefeatWatermarker is a defensive watermark and provenance robustness lab for evaluating how machine-readable AI provenance signals survive ordinary content transformations.

It is intentionally a **test harness, not a watermark-removal service**. The architecture keeps mutation logic separate from detector feedback, uses predefined/versioned scenarios, and reports robustness results without exporting transformed artifacts.

## Status

The current implementation provides:

- typed artifact, watermark-family, verification-state, detection, and evaluation models;
- read-only detector adapters and a machine-readable capability registry;
- conservative provenance/container hint discovery;
- optional standards-aware C2PA verification through the official `c2pa-python` Reader;
- explicit C2PA valid/trusted/invalid/error states and custom trust-anchor support;
- bounded provenance graphs for manifests and ingredients;
- a mutation interface with detector-blind transformations;
- non-destructive control mutations plus a fixed image platform-rendition suite;
- an evaluation engine where mutations never receive detector results;
- strict versioned robustness-suite documents with canonical SHA-256 digests;
- content-addressed evidence bundles binding artifact hash, suite hash, report hash, and aggregate results;
- separate survival metrics for detection, cryptographic verification, trust, and provenance identifiers;
- CI-style pass/fail/indeterminate gates;
- JSON-safe reports that contain no artifact or derivative bytes.

The evidence model deliberately borrows the strongest engineering pattern from the companion E2H project: important claims are bound to replayable/versioned inputs and content-addressed observable evidence rather than hidden state. Here, the immutable input is a robustness suite instead of an agent task capsule.

## Install

Core development environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
```

Optional runtime extras:

```bash
pip install -e '.[c2pa]'   # official C2PA Reader integration
pip install -e '.[image]'  # fixed image rendition suite
```

Inspect what is available in the current environment:

```bash
python -m defeat_watermarker capabilities
```

## Quick start

```bash
python -m defeat_watermarker scan path/to/asset.png --media-type image/png
python -m defeat_watermarker suite validate suites/control-v0.1.json
python -m defeat_watermarker suite validate suites/image-platform-v0.1.json

python -m defeat_watermarker evaluate path/to/asset.png \
  --media-type image/png \
  --suite suites/image-platform-v0.1.json \
  --output .defeat-watermarker/evidence.json
```

C2PA signer trust can be evaluated against explicit PEM trust anchors:

```bash
python -m defeat_watermarker scan asset.jpg \
  --media-type image/jpeg \
  --c2pa-trust-anchors ./trust-anchors.pem
```

Remote C2PA manifest fetching remains disabled by default.

## CI gates

A fixed-suite result can become a CI exit status. Detection and stronger provenance assurances are independent thresholds:

```bash
python -m defeat_watermarker evaluate asset.jpg \
  --media-type image/jpeg \
  --suite suites/image-platform-v0.1.json \
  --min-survival-rate 1.0 \
  --min-verification-survival-rate 1.0 \
  --min-trust-survival-rate 1.0 \
  --min-provenance-id-preservation-rate 1.0
```

Exit code `2` means at least one requested threshold failed; `3` means a requested metric was indeterminate because there were not enough eligible baseline comparisons. A passing engineering gate is not a legal compliance certification.

## Content-addressed evaluation model

A suite has a canonical digest independent of JSON formatting. Evaluation produces an evidence bundle containing:

- SHA-256 and byte length of the input artifact, but not its bytes;
- suite ID, version, and canonical digest;
- report digest and structured detector comparisons;
- aggregate robustness/assurance metrics;
- a deterministic evidence ID covering the complete bundle core.

This lets CI, auditors, and future registries verify that two reports refer to the same asset and exact test suite without retaining transformed media.

## Design boundary

The core does not implement adaptive optimization against detectors, detector-gradient access, detector-guided mutation selection, or a `remove watermark` operation. Mutation implementations are selected before results are produced and only receive an artifact plus a predefined scenario. Evaluation reports expose evidence and confidence/assurance changes, not derivative artifact bytes.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`docs/C2PA.md`](docs/C2PA.md), and [`ROADMAP.md`](ROADMAP.md).
