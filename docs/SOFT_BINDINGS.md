# Soft-binding extractor boundary

Durable provenance can reconnect transformed media to provenance records through soft bindings such as invisible watermarks and perceptual fingerprints. DefeatWatermarker treats **extraction**, **resolution**, **manifest retrieval**, and **verification** as separate stages.

```text
artifact
  -> SoftBindingExtractor
  -> opaque SoftBinding
  -> resolver match
  -> candidate manifest identifier
  -> bounded manifest retrieval
  -> C2PA validation/trust
```

`SoftBindingExtractor` is the extension point for future watermark/fingerprint schemes. An extractor declares a stable ID, binding kind (`watermark`, `fingerprint`, or `other`), supported modalities, and returns bounded opaque `SoftBinding` values.

The raw binding value is intentionally not part of serialized extraction evidence. Evidence contains only:

- extractor ID and binding kind;
- algorithm identifier;
- SHA-256 query digest;
- binding byte length;
- source artifact SHA-256/length and media type.

No built-in extractor currently attempts to reverse engineer or neutralize unknown watermark signals. A future provider/standard adapter should add extraction only when the binding format and detector API are legitimately available, with fixtures documenting what is observable and what remains private.

The registry caps each extractor at 32 bindings per artifact. Resolution still requires an explicit resolver policy, and recovered candidates remain unverified until the normal provenance-validation stage succeeds.
