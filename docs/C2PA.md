# C2PA verification model

DefeatWatermarker treats C2PA as signed provenance, not as a generic metadata string.

## SDK integration

The optional `c2pa` extra installs the official `c2pa-python` SDK. The adapter uses the stream-based `Reader` API and records only a bounded summary of its public JSON report.

```bash
pip install -e '.[c2pa]'
python -m defeat_watermarker capabilities
python -m defeat_watermarker scan asset.jpg --media-type image/jpeg
```

The adapter reports these assurance states separately:

- `not_evaluated` — no manifest was found or this assurance mechanism was not applicable;
- `well_formed` — a manifest store was parseable but cryptographic validity was not established in the reported result;
- `valid` — the SDK reports cryptographic validity;
- `trusted` — the SDK reports validity and signer trust;
- `invalid` — a C2PA manifest was discovered but validation failed;
- `error` — verification could not be completed.

Detection confidence is not a substitute for cryptographic assurance. A discovered invalid manifest is still `detected=true`, while `cryptographically_verified=false`.

## Trust anchors

Custom trust anchors can be supplied explicitly as PEM certificates:

```bash
python -m defeat_watermarker scan asset.jpg \
  --media-type image/jpeg \
  --c2pa-trust-anchors ./trust-anchors.pem
```

The adapter maps these certificates to the SDK's `trust.user_anchors` setting, keeping the built-in trust store available while adding the caller's roots. The default local trust configuration accepts the document-signing and C2PA claim-signing EKUs. If the C2PA SDK is not installed, providing trust anchors fails closed rather than silently ignoring them.

The CLI does not accept arbitrary trust-settings JSON. More specialized trust policy can be supplied programmatically through `C2paTrustPolicy`, where a caller may provide an explicit EKU `trust_config`.

## Network boundary

Remote-manifest fetching is disabled by default and is not exposed as a CLI switch in the normal verifier. This keeps ordinary robustness tests local and deterministic. The separate recovery/resolver subsystem owns bounded network policy, endpoint allowlists, response-size limits, timeouts, and evidence for external lookups.

## Provenance graph

The C2PA adapter converts the Reader report into a bounded graph containing only selected fields:

- asset, manifest, and ingredient nodes;
- active/other manifest edges;
- ingredient relationships;
- title, media type, instance/document identifiers, claim-generator identity, and signer issuer/common-name fields.

It deliberately excludes arbitrary assertion bodies, thumbnail bytes, binary resources, and the raw manifest-store JSON. This keeps evidence useful for continuity analysis without turning every report into a full provenance-data export.

## Robustness metrics

C2PA evaluations track four independent continuity dimensions:

1. detection survival;
2. cryptographic-verification survival;
3. trusted-state survival;
4. provenance-identifier preservation.

A result can therefore remain detectable while failing a stronger assurance gate. That distinction is intentional.

## Real signed regression path

The C2PA CI job creates an end-to-end cryptographic regression asset on every pull request. No signing private key is stored in the repository.

The job:

1. creates an ephemeral P-256 root and signing certificate;
2. emits the leaf private key as PKCS#8 for the official SDK signer;
3. signs a deterministic JPEG with a V2 `c2pa.created` action and explicit IPTC `digitalSourceType`;
4. verifies the signed asset through `defeat-watermarker-ui` using the ephemeral root as an additional trust anchor;
5. flips one byte in the JPEG entropy-coded payload while preserving the embedded manifest container;
6. verifies that the tampered asset is still discoverable as C2PA but fails cryptographic validation;
7. stores only the public certificates, JSON evidence, and fixture-generation metadata as CI artifacts.

The regression is intentionally stronger than the synthetic `C2PA` marker in `fixtures/retests/example_image.ppm`: the synthetic fixture tests metadata-hint survival, while this CI-generated fixture tests actual signature/trust/hard-binding behavior through the official SDK.

The expected validation distinction is:

```text
signed original: signing credential trusted + claim signature validated + data hash matched
tampered copy:   manifest still discoverable, but a hard-binding/hash mismatch makes it invalid
```

This gives the anti-watermark harness a stable cryptographic baseline before applying its fixed image rendition attacks.
