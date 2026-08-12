# Robustness regression baselines

Regression baselines protect fixed-suite results from silently degrading across releases.

A baseline is created only from an evidence document that passes offline self-consistency verification. It binds:

- the source evidence ID;
- exact robustness-suite digest;
- adapter-runtime digest;
- every available aggregate survival-rate metric;
- an explicit maximum allowed drop for each metric.

Create a baseline:

```bash
defeat-watermarker-regression baseline .defeat-watermarker/evidence.json \
  --id image-c2pa-release \
  --version 2026.08 \
  --max-drop 0.02 \
  --output baselines/image-c2pa-release.json
```

The emitted baseline file follows the published `regression-baseline-v0.1` schema exactly. Its content digest is derived when a comparison report is created rather than stored as a self-referential field in the baseline document.

Compare later evidence and retain the content-addressed report:

```bash
defeat-watermarker-regression check \
  baselines/image-c2pa-release.json \
  .defeat-watermarker/current-evidence.json \
  --output regression-report.json
```

A comparison passes only when the suite and detector-runtime digests match and every available metric remains within its configured drop. A suite or detector-runtime change produces `indeterminate`, not `pass` or `fail`, because the experimental conditions changed. Missing metrics are also indeterminate.

Exit code `6` means a comparable metric regression exceeded its allowed drop. Exit code `7` means the comparison was indeterminate.

## Verify a saved report

A saved regression report can be independently recomputed from the baseline and current evidence:

```bash
defeat-watermarker-regression verify \
  baselines/image-c2pa-release.json \
  .defeat-watermarker/current-evidence.json \
  regression-report.json
```

Verification loads the baseline, verifies the current evaluation evidence, recomputes the full regression comparison, and requires the saved report to match exactly. This is stronger than checking `report_id` alone: changing a metric/status/reason and recomputing the top-level hash is still rejected because the semantics no longer match the baseline/evidence inputs.

A valid saved report returns exit code `0`; a report that fails recomputation verification returns exit code `8`. Verification output can be written with `--output`, but the command refuses to overwrite the baseline, evidence or report inputs.

A regression baseline is not a quality target: freezing a weak result only proves it did not get worse. Regulatory/readiness thresholds and representative reliability/interoperability evidence remain separate concerns.
