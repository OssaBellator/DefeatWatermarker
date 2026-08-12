# Provider detector conformance

`defeat-watermarker-detector-conformance` qualifies one explicitly enabled read-only detector plugin against a fixed local artifact. It does **not** load mutation code, choose attacks, or optimize content against detector feedback.

## Run

```bash
defeat-watermarker-detector-conformance run \
  fixtures/retests/example_text.txt \
  --media-type text/plain \
  --detector-plugin fixture-text \
  --output conformance.json
```

A passing run checks that:

- the adapter runtime identity is bounded, deterministic before detection, and unchanged after detection;
- repeated `capabilities()` calls are deterministic;
- the adapter declares `detect` and does not expose a `remove` capability or method;
- repeated `supports()` calls for the same artifact are deterministic and return booleans;
- the adapter supports the supplied artifact modality;
- `detect()` returns a `DetectionResult` whose `adapter_id` and watermark family match the adapter;
- two detector calls over identical source state produce identical evidence;
- the artifact byte hash, byte length, media type, name and modality remain unchanged after `supports()` and after each detector call;
- the emitted detection object follows the strict bounded `DetectionResult` evidence shape.

The source bytes and source name are not embedded in the report. The artifact is represented by SHA-256, byte length, media type and modality; the name is compared only inside the conformance process to detect plugin-side mutation.

This is a contract check, not a security sandbox. Explicitly loading a detector plugin executes local third-party Python code, so plugin packages still need the same trust/review treatment as other executable dependencies.

## Verify

```bash
defeat-watermarker-detector-conformance verify conformance.json
```

Verification recomputes the content-addressed `report_id`, validates all bounded field structures and checks pass/fail semantics independently. Rehashing a report after deleting a required check or adding arbitrary detection fields does not make it valid.

Exit codes:

- `0`: conformance passed / report verification succeeded;
- `2`: the detector loaded but failed one or more conformance checks;
- `4`: conformance evidence failed offline verification;
- argparse errors are used for malformed input or plugin-loading failures.

## Runtime identity

Provider adapters may expose:

```python
def runtime_identity(self):
    return (
        "model=checkpoint-2026-08-12",
        "threshold-profile=balanced-v2",
    )
```

Those strings become part of the conformance report and all normal detector evidence. The hook is descriptive only: do not expose secrets, keys, weights, gradients, detector locations or other sensitive internals.

The conformance runner samples this identity before detector calls and again afterward. A detector that changes its declared model/configuration identity as a side effect of detection fails qualification.

## Static report

Verified conformance evidence can be rendered locally:

```bash
defeat-watermarker-report conformance.json --output conformance.html
```

The renderer verifies the JSON first and emits no JavaScript, network references, source bytes or transformed media.

## Local regression

The checked-in synthetic provider plugin is exercised end to end with:

```bash
bash scripts/test/conformance.sh
```

That script loads the plugin by its installed entry point, runs conformance, verifies the resulting JSON, renders the HTML view and asserts the static-report boundary plus all required state/determinism checks.
