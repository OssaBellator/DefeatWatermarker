# Roadmap

DefeatWatermarker follows an evidence-first development model: fixed evaluation inputs, content-addressed results, and explicit boundaries between transformation code and detector feedback.

## M0 — Foundation

- [x] Read-only detector adapter interface and registry
- [x] Typed artifacts, detections, scenarios, comparisons, and reports
- [x] Non-destructive control mutations
- [x] Detector/mutation feedback separation
- [x] Reports exclude derivative bytes
- [x] Source/derivative byte ceilings and atomic report writes

## M1 — Reproducible robustness evidence

- [x] Strict, versioned robustness-suite documents
- [x] Canonical suite digests
- [x] Artifact/report/suite content-addressed evidence bundles
- [x] Derivative hashes/lengths and mutation runtime identities without derivative export
- [x] Gate policy/results bound into evidence IDs
- [x] Offline evidence self-consistency verification
- [x] Detection and provenance-assurance survival summaries
- [x] CI-style gates
- [x] Built-in control suite
- [ ] Detached signed evidence manifests
- [ ] Golden fixtures for every supported detector family

## M2 — Standards-aware provenance

- [x] C2PA manifest discovery and cryptographic verification adapter
- [x] Trust-anchor configuration with explicit verification states
- [x] Bounded provenance evidence graph for manifests/ingredients
- [x] External soft-binding resolver interface with bounded network policy
- [x] Redacted soft-binding lookup/recovery evidence model
- [ ] Concrete C2PA Soft Binding Resolution API client
- [ ] Test vectors for valid, invalid, expired, trusted, and detached manifests

## M3 — Fixed modality suites

- [x] Image suite descriptors and deterministic in-memory transformations
- [x] Audio PCM-WAV suite with level/downmix/resample workflows
- [x] Text suite limited to non-semantic editorial normalization
- [x] Optional bounded FFmpeg video rendition suite
- [x] Transformation implementations remain predefined and detector-blind
- [x] No derivative chosen through detector-score optimization is exportable

## M4 — Interoperability and policy profiles

- [x] Machine-readable built-in capability registry
- [x] Versioned EU Article 50(2) provider-marking engineering profile
- [x] Capability/runnable-modality gap assessment with non-certification disclaimer
- [x] Fixed labelled-corpus false-positive/false-negative benchmark runner
- [ ] Representative reviewed reliability corpora for supported detector families
- [ ] Multi-provider detector adapters behind optional dependencies
- [ ] Versioned interoperability matrices
- [ ] Regression baselines suitable for release gates
