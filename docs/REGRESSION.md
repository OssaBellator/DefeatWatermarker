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

Compare later evidence:

```bash
defeat-watermarker-regression check \
  baselines/image-c2pa-release.json \
  .defeat-watermarker/current-evidence.json
```

A comparison passes only when the suite and detector-runtime digests match and every available metric remains within its configured drop. A suite or detector-runtime change produces `indeterminate`, not `pass` or `fail`, because the experimental conditions changed. Missing metrics are also indeterminate.

Exit code `6` means a comparable metric regression exceeded its allowed drop. Exit code `7` means the comparison was indeterminate.

A regression baseline is not a quality target: freezing a weak result only proves it did not get worse. Regulatory/readiness thresholds and representative reliability/interoperability evidence remain separate concerns.
