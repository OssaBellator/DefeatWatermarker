# DefeatWatermarker

DefeatWatermarker is a defensive watermark and provenance robustness lab for evaluating how machine-readable AI provenance signals survive ordinary content transformations.

It is intentionally a **test harness, not a watermark-removal service**. The architecture keeps mutation logic separate from detector feedback, uses predefined/versioned scenarios, and reports robustness results without exporting transformed artifacts.

## Status

This repository is at the foundation stage. The current implementation provides:

- typed artifact, watermark-family, detection, and evaluation models;
- a detector adapter interface and registry;
- a conservative container/provenance hint detector;
- a mutation interface with non-destructive control mutations;
- an evaluation engine where mutations never receive detector results;
- JSON-safe reports that contain no artifact bytes;
- a small `scan` CLI;
- unit tests and GitHub Actions CI.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
python -m defeat_watermarker scan path/to/asset.png
```

The built-in detector only reports recognizable provenance/container hints; it does **not** claim cryptographic verification. Future C2PA, perceptual-watermark, fingerprint, registry, audio, video, image, and text detectors should be added as independent adapters.

## Design boundary

The core does not implement adaptive optimization against detectors, detector-gradient access, or a "remove watermark" operation. Mutation implementations are selected before results are produced and only receive an artifact plus a predefined scenario. Evaluation reports expose evidence and confidence changes, not derivative artifact bytes.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the extension model.
