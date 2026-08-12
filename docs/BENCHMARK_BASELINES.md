# Benchmark regression baselines

DefeatWatermarker benchmark baselines turn verified detector reliability/interoperability reports into comparable release-regression evidence.

They are intentionally stricter than a normal "previous run vs current run" comparison: a result is comparable only when the labelled input definition and detector runtime identity are unchanged.

## Create a baseline

```bash
defeat-watermarker-benchmark-baseline create \
  reliability.json \
  --output reliability-baseline.json
```

The source report must pass `defeat-watermarker-benchmark-verify` semantics before it can become a baseline.

A baseline binds:

- benchmark type (`reliability` or `interoperability`);
- source `report_id`;
- exact corpus/matrix digest;
- digest of the complete detector runtime identity;
- normalized comparable metrics;
- content-addressed `baseline_id`.

Detector runtime identity includes the DefeatWatermarker/package/runtime identifiers and, for external detector plugins when resolvable, the distribution name/version. Providers may also expose bounded read-only configuration/model identifiers through `runtime_identity()`; those are hash-bound as `adapter-runtime=...` entries.

## Compare

```bash
defeat-watermarker-benchmark-baseline compare \
  current-reliability.json \
  --baseline reliability-baseline.json \
  --output comparison.json
```

Statuses:

- `same_or_better` — comparable run and no tracked metric regressed;
- `regression` — comparable run and at least one tracked metric regressed;
- `indeterminate` — experimental conditions changed, so a directional quality claim would be misleading.

Exit codes:

- `0` same or better;
- `2` regression;
- `3` indeterminate.

### Reliability comparison

Higher is better:

- accuracy;
- precision;
- recall;
- specificity.

Lower is better:

- false-positive rate;
- false-negative rate.

### Interoperability comparison

The adapter pair set and comparable case count must remain stable. For each pair, a lower agreement rate is a regression.

## Comparability failures

The comparison becomes `indeterminate` rather than pass/fail when:

- reliability vs interoperability type changes;
- corpus/matrix digest changes;
- detector runtime identity changes.

This matters for provider detectors: a new model checkpoint, key/profile version, detector package release, or declared configuration identity should not be silently judged against an old baseline as though it were the same implementation.

## Content-addressed comparison evidence

Comparison output is itself a portable evidence object:

```json
{
  "comparison_id": "...sha256...",
  "schema_version": "0.1",
  "status": "same_or_better",
  "baseline_id": "...sha256...",
  "report_id": "...sha256...",
  "changes": [],
  "reason": "no comparable benchmark metric regressed"
}
```

Verify it independently:

```bash
defeat-watermarker-benchmark-baseline verify-comparison comparison.json
```

The verifier checks exact fields, status/change semantics and `comparison_id`. A regression must have at least one change; `same_or_better` and `indeterminate` must not carry hidden regression changes.

Schemas:

- `schemas/benchmark-baseline-v0.1.schema.json`
- `schemas/benchmark-comparison-v0.1.schema.json`

## CI

`benchmark-ci.yml` exercises provider reliability/interoperability and creates runtime-aware baselines.

`benchmark-baseline-ci.yml` additionally persists and verifies content-addressed comparison evidence so the CI decision has an auditable record beyond the command exit code.
