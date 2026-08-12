# Soft-binding resolver boundary

C2PA durable provenance can use soft bindings such as fingerprints or invisible watermarks to recover a manifest that is no longer embedded with an asset. DefeatWatermarker models that recovery path separately from local C2PA validation.

## v1 contract

The resolver contract is deliberately **by-binding only**:

```text
artifact
  -> local soft-binding detector/extractor
  -> opaque SoftBinding
  -> approved resolver
  -> candidate manifest identifiers
  -> manifest retrieval under separate policy
  -> normal C2PA validation/trust
```

A `SoftBindingResolver` never receives artifact bytes. It receives only an already-extracted algorithm identifier and opaque binding value. Serialized evidence contains a SHA-256 query digest and binding length, not the raw binding value.

## C2PA Soft Binding Resolution API client

`C2paSoftBindingHttpResolver` implements only `POST /matches/byBinding`. The request follows the C2PA 2.4 schema: algorithm ID plus base64-encoded binding value. Returned `manifestId`, optional endpoint, and optional 0–100 similarity score become bounded candidate references.

The concrete transport:

- requires an explicitly allowlisted HTTPS endpoint;
- rejects URL userinfo/query/fragment in configured base endpoints;
- disables environment proxies and automatic redirects;
- sets a request timeout;
- checks declared and actual response byte limits;
- requires `application/json` and bounded JSON response structure;
- requests no more than the policy match limit;
- never follows a match endpoint automatically;
- drops returned endpoints that are outside the allowlist;
- supports an optional bearer token that is never serialized into resolver results.

The resolution service necessarily receives the soft-binding algorithm and binding value because those fields are the lookup query. It does **not** receive the source artifact through this interface.

## Recovery is not verification

A resolver match is only a candidate manifest identifier. Similarity score is not cryptographic verification. Recovered manifests must still be fetched under a separate bounded policy and pass the ordinary C2PA validity/trust pipeline before stronger provenance claims are made.
