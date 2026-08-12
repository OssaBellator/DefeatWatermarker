# Detached evidence signatures

Content addressing proves internal byte identity; it does not identify who approved or published an evidence bundle. The optional signing layer adds a detached Ed25519 signature over the already-verified evaluation-evidence ID.

Install the signing extra:

```bash
pip install -e '.[signing]'
```

## Sign

Use an unencrypted Ed25519 private key in PEM/PKCS#8 form:

```bash
defeat-watermarker-signature sign evidence.json \
  --private-key release-ed25519.pem \
  --key-id release-2026 \
  --output evidence.sig.json
```

Omit `--output` to emit the detached signature JSON to stdout. The signer first performs normal evidence self-consistency verification, so invalid or internally inconsistent evidence is not signed.

The detached signature document records the content-addressed `signature_id`, evidence ID, human-managed key ID, public-key SHA-256 fingerprint, algorithm and base64 signature. Ed25519 signature payloads are required to be exactly 64 bytes, and private-key bytes are never serialized.

On POSIX systems the signing command refuses a private-key file that is group/world readable or writable. When `--output` is supplied, the command also refuses a path that aliases either the evidence input or the private-key input, preventing accidental overwrite of signing material.

## Verify

```bash
defeat-watermarker-signature verify \
  evidence.json \
  evidence.sig.json \
  --public-key release-ed25519.pub.pem
```

Verification checks the evidence document, detached signature document, public-key fingerprint and Ed25519 signature. By default the verification JSON is emitted to stdout; `--output` writes it atomically to a file. A verification output is not allowed to alias the evidence, detached-signature, or public-key input.

A valid verification returns exit code `0`; a cryptographic or fingerprint mismatch returns exit code `8`. Malformed input uses the normal argparse error path.

The current implementation accepts unencrypted PEM Ed25519 private keys. Deployments with stronger key-management requirements should place signing behind an HSM/KMS-backed release step rather than copying private material into automation workspaces.

A valid signature proves only that the holder of the corresponding key signed that evidence ID. Trust in the key identity, release process, detector implementation and underlying robustness evidence remains an external policy decision. This mechanism is separate from C2PA signatures carried by media assets themselves.

## Local regression

The optional local signing suite exercises both the library and canonical CLI paths with ephemeral keys:

```bash
bash scripts/test/signing.sh
```

The tests cover successful sign/verify, stdout/file output, wrong-key rejection, strict detached-document parsing, private-material exclusion and input-overwrite protection.
