# Batch artifact regression

`defeat-watermarker-batch` runs the same detector and fixed-suite machinery across a bounded local artifact set. It is intended for regression corpora, provider detector comparisons and CI fixtures—not for adaptive attack search.

## Run a mixed batch

```bash
defeat-watermarker-batch ./fixtures/retests \
  --output-dir /tmp/dwm-batch
```

Known image/audio/video/text modalities use their built-in immutable attack suite. Files without a built-in suite fall back to detector-only scan evidence.

Force every artifact into detector-only mode:

```bash
defeat-watermarker-batch ./corpus \
  --scan-only \
  --output-dir /tmp/dwm-scan-batch
```

Explicit provider detectors can be enabled exactly as in the single-artifact CLIs:

```bash
defeat-watermarker-batch ./corpus \
  --detector-plugin provider-text-v1 \
  --output-dir /tmp/provider-regression
```

## Output layout

```text
output-dir/
  batch.json
  records/
    <record-id>.json
    <record-id>.json
```

`batch.json` is content-addressed by `batch_id`. Each successful entry contains a `record_id` that is either an evaluation `evidence_id` or detector-only `scan_id`. Record filenames are exactly `<record_id>.json`, so file naming adds no unbound identity layer.

The batch index does not contain source or derivative bytes. Individual evaluation records preserve the existing derivative-hash-only boundary.

## Offline verification

Verify the index and every referenced record together:

```bash
defeat-watermarker-batch-verify /tmp/dwm-batch
```

The verifier:

1. recomputes `batch_id`;
2. checks the strict index shape and bounded record count;
3. loads `records/<record_id>.json`;
4. dispatches `scan` records to the scan verifier;
5. dispatches `attack` records to the evaluation-evidence verifier;
6. checks that the verified record's own ID matches the ID bound by the batch index.

Changing a detector confidence, source reference, attack report or batch-index field after generation therefore invalidates the appropriate content-addressed layer.

## Bounds and path policy

The batch runner deliberately rejects or limits several filesystem cases:

- at most 64 regular input files;
- at most 256 MiB of total source data;
- individual artifacts remain subject to the core artifact-size ceiling;
- symlink input roots are rejected and symlink files are skipped;
- recursion is opt-in with `--recursive`;
- the output directory must be outside a directory input tree;
- an existing output directory must be empty;
- an output directory may not itself be a symlink.

These rules prevent accidental self-ingestion, stale-evidence mixing and unbounded directory walks.

## CI

`.github/workflows/batch-ci.yml` runs two permanent fixture batches:

- detector-only mode across the fixture directory;
- mixed fixed-attack mode, with the synthetic text detector explicitly enabled.

Both outputs are verified through the installed batch verifier and retained as workflow artifacts for inspection.
