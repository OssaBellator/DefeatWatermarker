# Soft-binding resolver boundary

C2PA durable provenance can use soft bindings such as fingerprints or invisible watermarks to recover a manifest that is no longer embedded with an asset. DefeatWatermarker models that recovery path separately from local C2PA validation.

## v1 contract

The first resolver contract is deliberately **by-binding only**:

```text
artifact
  -> local soft-binding detector/extractor
  -> opaque SoftBinding
  -> approved resolver
  -> manifest references
  -> normal C2PA validation
```

A `SoftBindingResolver` never receives the artifact bytes. It receives only an already-extracted algorithm identifier and opaque binding value. Serialized evidence contains a SHA-256 query digest and binding length, not the raw binding value.

## Network policy

Every network-capable resolver implementation must receive an explicit `ResolverPolicy` containing:

- an allowlist of bounded HTTPS endpoints;
- timeout ceiling;
- response-size ceiling;
- maximum match count;
- an explicit prohibition on artifact upload in the v1 contract.

The repository currently provides the interface, registry, policy, and evidence types but no default network resolver. A concrete Soft Binding Resolution API client should be added only with fixtures and adversarial tests for endpoint enforcement, redirects, response limits, parser bounds, and provenance re-validation.

## Recovery is not verification

A resolver match is only a candidate provenance reference. Recovery does not itself establish cryptographic validity or trust. Any recovered C2PA manifest still has to pass the ordinary C2PA validation/trust pipeline, and the evaluation should record that distinction.
