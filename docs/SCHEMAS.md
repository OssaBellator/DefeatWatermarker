# Machine-readable schemas

The `schemas/` directory publishes JSON Schema draft 2020-12 descriptions for the repository's portable configuration and release-artifact formats.

Current schemas cover:

- robustness suites;
- engineering-readiness profiles;
- detector reliability corpora;
- interoperability matrices;
- robustness regression baselines;
- detached evidence signatures.

The Python loaders remain the normative implementation for semantic checks that are awkward or inappropriate to encode in JSON Schema. Examples include path containment after symlink resolution, runtime capability availability, content-addressed digest verification, duplicate semantic identities, cryptographic verification, and the relationship between an evidence bundle and the exact suite it references.

Schemas are therefore intended for editor/tooling interoperability and early structural validation, not as a way to bypass the stricter runtime validation path.

All published root schemas use `additionalProperties: false` so future fields require an explicit schema/version change rather than being silently ignored.
