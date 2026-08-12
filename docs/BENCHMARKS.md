# Detector reliability and interoperability benchmarks

DefeatWatermarker treats detector quality as a separate evidence problem from attack robustness.

The benchmark subsystem does not tune detector thresholds or choose attacks from benchmark results. It evaluates fixed, labelled corpora and fixed multi-adapter matrices.

## Reliability

A reliability corpus names one exact adapter and labels each artifact as expected detected/not-detected:

```bash
defeat-watermarker benchmark reliability \
  fixtures/benchmarks/text-detectors/reliability-v0.1.json \
  --detector-plugin fixture-text \
  --output reliability.json
```

Reports include:

- source artifact hashes/lengths, never source bytes;
- expected and actual detection state;
- confidence and verification state;
- TP/TN/FP/FN;
- accuracy, precision, recall, specificity, FPR and FNR;
- exact detector runtime identity, including external distribution/version when resolvable;
- a content-addressed `report_id`.

The report schema is `schemas/reliability-report-v0.2.schema.json`.

## Interoperability

An interoperability matrix names two or more exact adapters and runs each supported detector against the same fixed cases:

```bash
defeat-watermarker benchmark interoperability \
  fixtures/benchmarks/text-detectors/interoperability-v0.1.json \
  --detector-plugin fixture-text \
  --detector-plugin fixture-text-secondary \
  --output interoperability.json
```

The report preserves per-case observations and computes pairwise detection agreement. Every adapter's runtime identity is bound into the report ID so detector upgrades are not silently compared as the same experimental condition.

The report schema is `schemas/interoperability-report-v0.2.schema.json`.

## Offline verification

Both report types use the same verifier:

```bash
defeat-watermarker-benchmark-verify reliability.json
defeat-watermarker-benchmark-verify interoperability.json
```

The verifier checks the exact report shape, schema version, corpus/matrix digest shape, runtime bounds, case structure and `report_id` binding. Modifying summary metrics or pairwise agreement values after generation invalidates the report ID.

## Static reports

Verified benchmark JSON can be rendered through the normal report command:

```bash
defeat-watermarker-report reliability.json --output reliability.html
defeat-watermarker-report interoperability.json --output interoperability.html
```

As with other reports, HTML rendering verifies the content-addressed input first and does not embed source artifacts, JavaScript or network resources.

## Provider fixture benchmarks

`fixtures/benchmarks/text-detectors/` is a synthetic regression set for the explicit detector-plugin seam.

The separately packaged fixture plugin exposes:

- `fixture-text` → `fixture.text-marker.v1`;
- `fixture-text-secondary` → `fixture.text-secondary.v1`.

The reliability corpus has one positive and one negative case and is expected to produce 1 TP, 1 TN, 0 FP and 0 FN.

The interoperability matrix contains:

1. a case detected by both fixture adapters;
2. a deliberate primary-only disagreement;
3. a case detected by neither adapter.

Expected pairwise result: 3 comparable cases, 2 agreements, 1 disagreement, agreement rate 2/3.

These detectors and corpora prove the benchmark/plugin contracts only. They are not production watermark detectors and do not establish real-world detector quality.

## CI

`.github/workflows/benchmark-ci.yml` installs the fixture detector package separately, explicitly enables the named plugins, runs both benchmark types, verifies both report IDs, renders both static HTML reports and checks the exact labelled metrics/runtime package version.
