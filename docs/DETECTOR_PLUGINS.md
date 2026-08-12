# Detector plugins

DefeatWatermarker supports provider- or research-specific **read-only detector adapters** through Python package entry points.

The entry-point group is:

```text
defeat_watermarker.detectors
```

Detector plugins are not loaded automatically. Installed entry points can be inspected without importing plugin code:

```bash
defeat-watermarker-ui --list-detector-plugins
```

A detector is loaded only when it is named explicitly:

```bash
defeat-watermarker-ui artifact.txt \
  --media-type text/plain \
  --detector-plugin provider-text-v1 \
  --json-output evidence.json
```

The option is repeatable when an experiment intentionally compares multiple installed detectors.

## Plugin contract

An entry point must resolve to one of:

- a `WatermarkAdapter` instance;
- a `WatermarkAdapter` subclass with a no-argument constructor; or
- a no-argument factory returning a `WatermarkAdapter`.

Each adapter provides a stable `adapter_id`, watermark/provenance family, supported modalities and a read-only `detect(Artifact) -> DetectionResult` implementation.

Example package metadata:

```toml
[project.entry-points."defeat_watermarker.detectors"]
provider-text-v1 = "provider_detector:ProviderTextDetector"
```

## Trust boundary

Entry-point discovery reads installed package metadata but does not import detector code. Loading executes code from the named installed package, so `--detector-plugin` should be treated like explicitly enabling any other local plugin.

The core intentionally does **not** expose a matching external mutation-plugin group. Attack transformations remain reviewed, fixed implementations owned by the harness. This prevents a detector package from quietly injecting detector-guided mutation or removal logic into the attack engine.

Detector adapters also do not receive mutation objects, mutation selection state or previous detector results. They receive only the artifact being inspected.

## Regression fixture

`fixtures/plugins/example_text_detector` is a separately packaged synthetic detector used to test the extension seam. It recognizes a deterministic marker in `fixtures/retests/example_text.txt` and is labelled as fixture-only in its detector warning. It is not a production text watermark detector.

CI explicitly installs and enables that fixture plugin, verifies that it survives the fixed editorial-normalization suite, and keeps the emitted evidence bundle as a workflow artifact.
