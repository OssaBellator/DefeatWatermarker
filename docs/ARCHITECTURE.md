# Architecture

## Goal

The project measures the durability of AI provenance and watermark signals under predefined transformations. It treats watermark technologies as interchangeable detection adapters rather than assuming one permanent marking scheme.

## Flow

```text
Artifact
  -> read-only detector registry -> baseline evidence
  -> predefined mutation scenario -> derivative held in memory
  -> same read-only detector registry -> post-mutation evidence
  -> comparison/report (no derivative bytes)
```

## Extension points

### Detection adapters

Implement `WatermarkAdapter` for standards-aware or vendor-specific detection. Candidate families include metadata, signed provenance, perceptual marks, statistical text marks, fingerprints, external registries, and hardware attestations.

Adapters should be read-only. A detector may verify cryptographic or external evidence, but mutation implementations must not receive detector objects or detector outputs.

### Mutations

Implement `ArtifactMutation` for a versioned, predefined robustness scenario. A mutation receives only an `Artifact` and `MutationScenario`. It does not receive confidence scores, watermark locations, gradients, extracted keys, or prior detector feedback.

The foundation release includes only control mutations. Media-specific transformation suites should be reviewed before addition and should model ordinary processing workflows rather than optimize toward detector failure.

### Reports

`EvaluationReport.to_dict()` intentionally serializes metadata and detection comparisons only. It does not include source or derivative artifact bytes.

## Planned adapters

- C2PA/Content Credentials verification;
- image/video perceptual watermark detectors through provider SDK adapters;
- audio watermark detectors;
- text statistical-signal detectors;
- perceptual fingerprint lookups;
- external provenance registry resolvers.

## Planned robustness metrics

- per-adapter survival rate;
- confidence change by scenario and generation;
- provenance continuity/recovery status;
- false-positive/false-negative test vectors;
- cross-adapter disagreement;
- regression thresholds suitable for CI.

## Safety boundary

The core intentionally omits watermark removal, adaptive search against a detector, gradient/score feedback into transformations, and derivative export. This keeps the project useful for provider/compliance red-teaming without shipping a turnkey provenance-evasion loop.
