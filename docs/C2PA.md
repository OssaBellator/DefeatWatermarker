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

Supplying trust anchors enables certificate-anchor verification for that run. If the C2PA SDK is not installed, providing trust anchors fails closed rather than silently ignoring them.

## Network boundary

Remote-manifest fetching is disabled by default and is not exposed as a CLI switch in the current release. This keeps ordinary robustness tests local and deterministic. A future resolver subsystem should have a separate bounded network policy, explicit endpoint allowlists, response-size limits, timeouts, and evidence for every external lookup.

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
