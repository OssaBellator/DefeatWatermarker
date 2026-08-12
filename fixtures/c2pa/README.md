# C2PA cryptographic regression fixture

This directory contains only the **public recipe** for the real C2PA regression path. No long-lived signing key or pre-signed media is stored in the repository.

`openssl-fixture.cnf` defines the certificate extensions used by the GitHub Actions `c2pa-sdk` job. On every run, CI generates fresh ephemeral P-256 credentials and then calls:

```bash
python scripts/generate_c2pa_retest_fixture.py ...
```

The generator starts from the deterministic image in `fixtures/retests/example_image.ppm`, converts it to JPEG, signs it through the official `c2pa-python` SDK and creates a second copy with one byte changed in the JPEG entropy-coded payload.

The signed manifest follows the current V2 example shape:

```text
c2pa.created
digitalSourceType = .../digitalCreation
```

The normal verifier is then expected to distinguish:

- **signed original** — manifest detected, signing credential trusted, claim signature validated, hard binding/data hash matched;
- **tampered copy** — manifest still detected, but hard-binding validation fails and the overall verification state is invalid.

The test deliberately keeps these concepts separate from the static PPM comment fixture. A string containing `C2PA` proves only that discovery-hint handling works; the CI-generated signed asset proves that the actual cryptographic validator and trust configuration work.

## CI artifacts

The `c2pa-regression-evidence` workflow artifact contains only public/non-secret diagnostic material:

- fixture-generation metadata;
- signed evaluation JSON evidence;
- tampered scan JSON;
- ephemeral root and leaf public certificates.

Private keys and signed/tampered media are not uploaded by the workflow.
