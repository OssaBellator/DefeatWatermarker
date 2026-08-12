# Static HTML reports

`defeat-watermarker-report` turns verified DefeatWatermarker JSON evidence into a self-contained local HTML report.

It accepts three input types:

```bash
# detector-only scan
defeat-watermarker-report scan.json --output scan-report.html

# fixed attack/evaluation evidence
defeat-watermarker-report evidence.json --output attack-report.html

# verified batch directory
defeat-watermarker-report /tmp/dwm-batch --output batch-report.html
```

The renderer verifies integrity **before** rendering:

- scan input must have a valid `scan_id`;
- evaluation input must have a valid `evidence_id` and report digest;
- batch input must have a valid `batch_id` and every referenced scan/evaluation record must verify independently.

If verification fails, no report is produced.

## Report boundary

The report is intentionally static and local:

- no JavaScript;
- no network requests;
- no remote fonts/styles/images;
- no source artifact bytes;
- no transformed derivative bytes;
- all evidence-originated text is HTML escaped.

The HTML therefore acts as a readable view over already-verified evidence rather than a second source of truth.

## Contents

Scan reports show the source reference, detector identities, detected state, confidence, verification state and provenance identifier.

Attack reports additionally show each fixed scenario, per-adapter detection survival, confidence delta, cryptographic/trust continuity and provenance-ID preservation, plus aggregate survival metrics.

Batch reports show each relative artifact path, selected mode (`attack`, `scan`, or `error`) and the content-addressed record ID. Detailed per-artifact data remains in the batch `records/` directory and is already bound by the batch verifier.

## CI

The permanent batch workflow renders a verified mixed batch and checks that the resulting HTML contains no script tag or HTTP/HTTPS references before retaining it alongside the evidence bundle.
