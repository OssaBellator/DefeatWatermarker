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

A provider may also expose an optional no-argument `runtime_identity()` method returning a bounded iterable of short strings. Use it for experiment-critical configuration that package/class identity alone does not capture, for example:

```python
def runtime_identity(self):
    return (
        "model=checkpoint-2026-08-12",
        "threshold-profile=balanced-v2",
        "key-profile=provider-keyset-4",
    )
```

DefeatWatermarker prefixes these values with `adapter-runtime=` and binds them into scan, attack, batch, benchmark and detector-conformance evidence. This makes a detector-model/configuration change visible to regression baselines instead of silently comparing unlike experiments.

The hook is intentionally small and descriptive: at most eight non-empty single-line strings, each at most 256 characters. Invalid, over-limit or failing runtime identity hooks abort evidence generation rather than being silently omitted. Do not expose keys, model weights, gradients, detector locations or other secrets through this hook.

Example package metadata:

```toml
[project.entry-points."defeat_watermarker.detectors"]
provider-text-v1 = "provider_detector:ProviderTextDetector"
```

## Conformance qualification

Before using a provider detector in robustness benchmarks, run the detector-only conformance command against a representative fixed artifact:

```bash
defeat-watermarker-detector-conformance run \
  artifact.txt \
  --media-type text/plain \
  --detector-plugin provider-text-v1 \
  --output conformance.json

defeat-watermarker-detector-conformance verify conformance.json
```

A passing report proves the adapter surface is read-only, the supplied modality is supported, result identity/family match the adapter, repeated detection over identical bytes is deterministic, source bytes remain unchanged, runtime identity is stable/bounded, and the emitted detection evidence has the strict `DetectionResult` shape.

The conformance runner contains no mutation registry and no detector-guided content modification path. See [`DETECTOR_CONFORMANCE.md`](DETECTOR_CONFORMANCE.md).

## Trust boundary

Entry-point discovery reads installed package metadata but does not import detector code. Loading executes code from the named installed package, so `--detector-plugin` should be treated like explicitly enabling any other local plugin.

The core intentionally does **not** expose a matching external mutation-plugin group. Attack transformations remain reviewed, fixed implementations owned by the harness. This prevents a detector package from quietly injecting detector-guided mutation or removal logic into the attack engine.

Detector adapters also do not receive mutation objects, mutation selection state or previous detector results. They receive only the artifact being inspected.

## Regression fixture

`fixtures/plugins/example_text_detector` is a separately packaged synthetic detector used to test the extension seam. It recognizes deterministic markers in the checked-in text fixtures and publishes explicit fixture profile identifiers through `runtime_identity()`. It is not a production text watermark detector.

The local test runners under `scripts/test/` explicitly install/enable that fixture plugin, qualify it with `scripts/test/conformance.sh`, verify its fixed editorial-normalization behavior, benchmark it against labelled cases, and bind its package plus runtime profile into the resulting evidence. GitHub Actions is intentionally disabled on the current feature branch while hosted-runner quota is unavailable.
