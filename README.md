# DefeatWatermarker

DefeatWatermarker is a defensive watermark and provenance robustness lab for evaluating how machine-readable AI provenance signals survive ordinary content transformations.

It is intentionally a **test harness, not a watermark-removal service**. The architecture keeps mutation logic separate from detector feedback, uses predefined/versioned scenarios, and reports robustness results without exporting transformed artifacts.

## Status

The current implementation provides:

- typed artifact, watermark-family, detection, and evaluation models;
- a read-only detector adapter interface and registry;
- a conservative container/provenance hint detector;
- a mutation interface with non-destructive control mutations;
- an evaluation engine where mutations never receive detector results;
- strict versioned robustness-suite documents with canonical SHA-256 digests;
- content-addressed evidence bundles binding artifact hash, suite hash, report hash, and aggregate results;
- survival metrics and CI-style pass/fail/indeterminate gates;
- JSON-safe reports that contain no artifact or derivative bytes;
- `scan`, `suite validate`, and `evaluate` CLI workflows;
- unit tests and GitHub Actions CI.

The evidence model deliberately borrows the strongest engineering pattern from the companion E2H project: important claims are bound to replayable/versioned inputs and content-addressed observable evidence rather than hidden state. Here, the immutable input is a robustness suite instead of an agent task capsule.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest

python -m defeat_watermarker scan path/to/asset.png --media-type image/png
python -m defeat_watermarker suite validate suites/control-v0.1.json
python -m defeat_watermarker evaluate path/to/asset.png \
  --media-type image/png \
  --suite suites/control-v0.1.json \
  --output .defeat-watermarker/evidence.json
```

An optional gate can turn a fixed-suite result into a CI exit status:

```bash
python -m defeat_watermarker evaluate path/to/asset.png \
  --suite suites/control-v0.1.json \
  --min-survival-rate 1.0
```

Exit code `2` means the requested survival threshold failed; `3` means the result was indeterminate because there were not enough baseline-detected marks to evaluate. A passing engineering gate is not a legal compliance certification.

## Content-addressed evaluation model

A suite has a canonical digest independent of JSON formatting. Evaluation produces an evidence bundle containing:

- SHA-256 and byte length of the input artifact, but not its bytes;
- suite ID, version, and canonical digest;
- report digest and structured detector comparisons;
- aggregate survival metrics;
- a deterministic evidence ID covering the complete bundle core.

This lets CI, auditors, and future registries verify that two reports refer to the same asset and exact test suite without retaining transformed media.

## Design boundary

The core does not implement adaptive optimization against detectors, detector-gradient access, detector-guided mutation selection, or a `remove watermark` operation. Mutation implementations are selected before results are produced and only receive an artifact plus a predefined scenario. Evaluation reports expose evidence and confidence changes, not derivative artifact bytes.

The built-in detector only reports recognizable provenance/container hints; it does **not** claim cryptographic verification. Future C2PA, perceptual-watermark, fingerprint, registry, audio, video, image, and text detectors should be added as independent adapters.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and [`ROADMAP.md`](ROADMAP.md).
