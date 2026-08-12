# Bounded C2PA manifest retrieval

Soft-binding resolution returns candidate manifest identifiers; those candidates are not provenance proof by themselves. The repository therefore keeps manifest retrieval as a separate stage from matching and from C2PA validation.

`C2paManifestHttpClient` implements only the C2PA Soft Binding Resolution API fetch route `GET /manifests/{manifestId}`. It requests `application/c2pa`, URL-encodes the manifest identifier as one path segment, and can explicitly request only the active manifest with `returnActiveManifest=true`.

The retrieval transport reuses the resolver policy for endpoint allowlisting, timeout and maximum response bytes. Environment proxies and automatic redirects are disabled. A returned match endpoint is usable only when it is explicitly in the policy allowlist.

Fetched C2PA bytes remain private in `FetchedManifestStore.data` (`repr=False`). Serializable evidence exposes only the manifest identifier, endpoint, media type, SHA-256 and byte length. Bearer credentials are never included in that reference.

Retrieval still does **not** imply validity or trust. The fetched bytes must be associated with the appropriate asset/manifest-validation workflow before a C2PA verification state is asserted. The current client intentionally does not auto-promote a resolver match or retrieved blob into a verified provenance claim.
