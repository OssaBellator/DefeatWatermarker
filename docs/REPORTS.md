# Static HTML reports

`defeat-watermarker-report` turns verified DefeatWatermarker evidence into a self-contained local HTML report.

Supported inputs:

```bash
# detector-only scan
defeat-watermarker-report scan.json --output scan-report.html

# fixed attack/evaluation evidence
defeat-watermarker-report evidence.json --output attack-report.html

# reliability or interoperability benchmark evidence
defeat-watermarker-report reliability.json --output reliability-report.html
defeat-watermarker-report interoperability.json --output interoperability-report.html

# provider detector conformance evidence
defeat-watermarker-report conformance.json --output conformance-report.html

# verified batch directory
defeat-watermarker-report /tmp/dwm-batch --output batch-report.html
```

The renderer verifies integrity **before** rendering:

- scan input must have a valid `scan_id`;
- evaluation input must have a valid `evidence_id` and report digest;
- benchmark input must have a valid `report_id` and pass independent reliability/pairwise metric consistency checks;
- detector conformance input must have a valid `report_id` and internally consistent pass/check semantics;
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

Reliability reports show labelled cases and recomputed accuracy/precision/recall/specificity/false-positive/false-negative rates. Interoperability reports show the verified pairwise comparable-case and agreement metrics.

Detector conformance reports show the explicitly enabled plugin/adapter, source hash reference, detected state/confidence and the passed read-only/determinism/runtime checks. Artifact bytes are not embedded.

Batch reports show each relative artifact path, selected mode (`attack`, `scan`, or `error`) and the content-addressed record ID. Detailed per-artifact data remains in the batch `records/` directory and is already bound by the batch verifier.

## Local regression checks

GitHub Actions is intentionally disabled on the current feature branch while hosted-runner quota is unavailable. The local runners verify the static-report boundary directly:

```bash
bash scripts/test/benchmarks.sh
bash scripts/test/conformance.sh
bash scripts/test/batch.sh
```

Those scripts reject report output containing script tags or HTTP/HTTPS references.
