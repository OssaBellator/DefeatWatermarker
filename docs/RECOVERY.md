# Content-addressed provenance recovery chains

Durable-provenance recovery is recorded as a chain of observable steps rather than collapsed into a single `verified` flag:

```text
artifact hash
  -> redacted extracted binding reference
  -> resolver query digest
  -> candidate manifest identifier(s)
  -> optional fetched manifest-store hash
  -> separate provenance verification stage
```

`build_recovery_chain` verifies that the selected binding came from the supplied extraction evidence and that the resolver algorithm/query digest match that exact binding. Any fetched manifest must correspond to a resolver candidate and, when the resolver supplied an endpoint, to the same endpoint.

The serialized chain contains no source artifact bytes, raw soft-binding values, bearer tokens, or fetched manifest bytes. It can include a similarity score because that is observable resolver output, but the chain is hard-coded as `candidate_only` in schema v0.1.

A high similarity score is not treated as cryptographic validity or signer trust. Those claims require a later asset-aware C2PA verification step, which remains deliberately separate from discovery and retrieval.
