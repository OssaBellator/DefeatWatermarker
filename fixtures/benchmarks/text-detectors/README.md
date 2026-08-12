# Synthetic provider detector benchmark fixtures

This directory exists only to regression-test DefeatWatermarker's explicit detector-plugin, reliability, interoperability, report-verification and static-report contracts.

It is **not** evidence of real-world watermark detector quality.

The separately installed package under `fixtures/plugins/example_text_detector/` exposes two entry points:

- `fixture-text` → adapter ID `fixture.text-marker.v1`, which detects the literal regression marker `DefeatWatermarker UI testing`;
- `fixture-text-secondary` → adapter ID `fixture.text-secondary.v1`, which detects the independent literal regression marker `DefeatWatermarker secondary detector marker`.

## Reliability corpus

`reliability-v0.1.json` targets only `fixture.text-marker.v1`.

Expected result:

```text
positive-primary.txt  expected=true   actual=true
negative.txt          expected=false  actual=false

TP=1 TN=1 FP=0 FN=0
```

## Interoperability matrix

`interoperability-v0.1.json` compares both fixture adapters:

```text
both.txt          primary=true   secondary=true    agreement
primary-only.txt  primary=true   secondary=false   deliberate disagreement
neither.txt       primary=false  secondary=false   agreement
```

Expected pairwise result:

```text
comparable_cases=3
agreements=2
disagreements=1
agreement_rate=2/3
```

The deliberate disagreement prevents this from becoming a ceremonial 100%-agreement smoke test and exercises pairwise consistency verification.

## Manual run

```bash
pip install -e '.[dev]' -e fixtures/plugins/example_text_detector

defeat-watermarker benchmark reliability \
  fixtures/benchmarks/text-detectors/reliability-v0.1.json \
  --detector-plugin fixture-text \
  --output /tmp/reliability.json

defeat-watermarker benchmark interoperability \
  fixtures/benchmarks/text-detectors/interoperability-v0.1.json \
  --detector-plugin fixture-text \
  --detector-plugin fixture-text-secondary \
  --output /tmp/interoperability.json

defeat-watermarker-benchmark-verify /tmp/reliability.json
defeat-watermarker-benchmark-verify /tmp/interoperability.json
```
