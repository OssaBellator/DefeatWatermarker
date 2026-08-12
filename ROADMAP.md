# Roadmap

DefeatWatermarker follows an evidence-first development model: fixed evaluation inputs, content-addressed results, and explicit boundaries between transformation code and detector feedback.

## M0 — Foundation

- [x] Read-only detector adapter interface and registry
- [x] Typed artifacts, detections, scenarios, comparisons, and reports
- [x] Non-destructive control mutations
- [x] Detector/mutation feedback separation
- [x] Reports exclude derivative bytes

## M1 — Reproducible robustness evidence

- [x] Strict, versioned robustness-suite documents
- [x] Canonical suite digests
- [x] Artifact/report/suite content-addressed evidence bundles
- [x] Survival summaries and CI-style gates
- [x] Built-in control suite
- [ ] Signed evidence manifests
- [ ] Golden fixtures for every supported detector family

## M2 — Standards-aware provenance

- [ ] C2PA manifest discovery and cryptographic verification adapter
- [ ] Trust-store configuration with explicit verification states
- [ ] Provenance evidence graph for compound/partial assets
- [ ] External resolver interface with bounded network policy
- [ ] Test vectors for valid, invalid, expired, and detached manifests

## M3 — Fixed modality suites

- [ ] Image suite descriptors and reproducible fixtures
- [ ] Video suite descriptors and reproducible fixtures
- [ ] Audio suite descriptors and reproducible fixtures
- [ ] Text/document editorial-survival suite descriptors
- [ ] Transformation implementations remain predefined and detector-blind
- [ ] No derivative chosen through detector-score optimization is exportable

## M4 — Interoperability and policy profiles

- [ ] Multi-provider detector adapters behind optional dependencies
- [ ] Versioned interoperability matrices
- [ ] EU Article 50 readiness profile as an engineering aid, explicitly not legal certification
- [ ] Regression baselines suitable for release gates
- [ ] Machine-readable capability registry
