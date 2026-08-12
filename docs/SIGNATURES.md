# Detached evidence signatures

Content addressing proves internal byte identity; it does not identify who approved or published an evidence bundle. The optional signing layer adds a detached Ed25519 signature over the already-verified evidence ID.

Install the signing extra:

```bash
pip install -e '.[signing]'
```

Create a detached signature:

```bash
defeat-watermarker-signature sign evidence.json \
  --private-key release-ed25519.pem \
  --key-id release-2026 \
  --output evidence.sig.json
```

Verify it:

```bash
defeat-watermarker-signature verify evidence.json evidence.sig.json \
  --public-key release-ed25519.pub.pem
```

The signer first performs normal evidence self-consistency verification. It then signs a domain-separated message containing the 32-byte evidence ID. The detached signature document records the evidence ID, human-managed key ID, public-key SHA-256 fingerprint, algorithm and signature. Private-key bytes are never serialized.

On POSIX systems the signing command refuses a private-key file that is group/world readable or writable. The current implementation accepts unencrypted PEM Ed25519 private keys; deployments with stronger key-management requirements should place signing behind an HSM/KMS-backed release step rather than copying private material into CI workspaces.

A valid signature proves only that the holder of the corresponding key signed that evidence ID. Trust in the key identity, release process, detector implementation and underlying robustness evidence remains an external policy decision.
