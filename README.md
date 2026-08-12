# DefeatWatermarker

DefeatWatermarker is an **anti-watermark red-team harness** for attacking the robustness of AI watermarking and provenance systems.

It sits on the adversarial side of the test: given an already-marked or provenance-bearing artifact, it runs reviewed hostile/real-world transformations and measures which detection and provenance guarantees survive. It is not a watermark generator.

The attack plan is fixed before detector results are produced. That makes results replayable across vendors and watermark versions instead of turning an experiment into a detector-specific optimization loop.

## What is implemented

The current implementation includes:

- typed artifacts, modalities, watermark families, verification states and bounded detection regions;
- read-only detector adapters and a machine-readable capability registry;
- conservative provenance/container hint discovery;
- optional C2PA verification through the official `c2pa-python` Reader;
- explicit C2PA valid/trusted/invalid/error states and custom trust-anchor support;
- bounded manifest/ingredient provenance graphs;
- bounded soft-binding lookup, manifest retrieval and candidate-only recovery evidence;
- detector-blind fixed attack mutations for image, audio, video and text;
- multi-generation image recompression plus resize/crop attacks;
- PCM-WAV level/downmix/resampling attacks;
- fixed FFmpeg H.264/AAC transcode and scale/transcode attacks;
- Unicode, line-ending and editor-cleanup text attacks;
- strict versioned robustness suites with canonical SHA-256 digests;
- content-addressed evidence bundles with offline integrity verification;
- separate survival metrics for detection, cryptographic verification, trust and provenance identifiers;
- labelled false-positive/false-negative reliability benchmarking;
- fixed multi-adapter interoperability matrices;
- regression baselines and CI-style pass/fail/indeterminate gates;
- an EU Article 50(2) provider-marking engineering-readiness profile that reports gaps rather than legal compliance.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
```

Optional integrations:

```bash
pip install -e '.[c2pa]'   # official C2PA Reader integration
pip install -e '.[image]'  # Pillow-backed image attack suite
```

Inspect the current detector and mutation environment:

```bash
defeat-watermarker capabilities
```

## Anti-watermark attack workflow

`defeat-watermarker-attack` is the adversarial entry point. It is an explicit alias for the fixed evaluator and inherits the same immutable-suite semantics.

```bash
defeat-watermarker-attack asset.jpg \
  --media-type image/jpeg \
  --suite suites/image-platform-v0.1.json \
  --output .defeat-watermarker/evidence.json
```

Available checked-in attack suites include:

```text
suites/image-platform-v0.1.json
suites/audio-pcm-workflow-v0.1.json
suites/video-platform-v0.1.json
suites/text-editorial-v0.1.json
```

An attack report can show, for example, that a mark remained detectable while its cryptographic provenance became invalid, that trust stopped surviving after a rendition, or that confidence degraded across repeated generations.

The transformed media itself is not emitted by the evaluator. Evidence records derivative hashes/runtime identity so results can be compared without publishing a derivative selected for detector failure.

See [`docs/ANTI_WATERMARKER.md`](docs/ANTI_WATERMARKER.md) for the threat model.

## General CLI

The normal CLI exposes the lower-level primitives directly:

```bash
defeat-watermarker scan asset.jpg --media-type image/jpeg

defeat-watermarker suite validate suites/image-platform-v0.1.json

defeat-watermarker evaluate asset.jpg \
  --media-type image/jpeg \
  --suite suites/image-platform-v0.1.json \
  --output evidence.json

defeat-watermarker evidence verify evidence.json \
  --suite suites/image-platform-v0.1.json
```

C2PA signer trust can be evaluated against explicit PEM trust anchors:

```bash
defeat-watermarker scan asset.jpg \
  --media-type image/jpeg \
  --c2pa-trust-anchors ./trust-anchors.pem
```

Remote C2PA manifest fetching remains disabled in the normal verifier unless a separate bounded resolver workflow is explicitly configured.

## CI attack gates

A fixed attack result can become a CI gate. Detection and stronger provenance assurances are separate thresholds:

```bash
defeat-watermarker-attack asset.jpg \
  --media-type image/jpeg \
  --suite suites/image-platform-v0.1.json \
  --min-survival-rate 1.0 \
  --min-verification-survival-rate 1.0 \
  --min-trust-survival-rate 1.0 \
  --min-provenance-id-preservation-rate 1.0
```

Exit code `2` means a requested threshold failed. Exit code `3` means a requested metric was indeterminate because there were not enough eligible baseline comparisons.

## EU Article 50 engineering profile

The repository includes a provider-side Article 50(2) **engineering-readiness** profile. It is an engineering aid, not legal certification.

```bash
defeat-watermarker profile validate \
  profiles/eu-article50-provider-marking-v0.1.json

defeat-watermarker profile assess \
  profiles/eu-article50-provider-marking-v0.1.json \
  --suite suites/image-platform-v0.1.json \
  --suite suites/audio-pcm-workflow-v0.1.json \
  --suite suites/video-platform-v0.1.json \
  --suite suites/text-editorial-v0.1.json
```

The profile is intentionally capable of remaining non-ready even when all modalities have suites; representative interoperability and reliability evidence are independent requirements.

## Evidence model

Evaluation evidence binds:

- SHA-256 and byte length of the source artifact, but not its bytes;
- the exact versioned attack suite and canonical suite digest;
- detector and mutation runtime identities;
- derivative SHA-256/length/media type, but not derivative bytes;
- baseline/post-attack detector evidence;
- detection, verification, trust and provenance-continuity metrics;
- requested gate policy/result;
- a deterministic evidence ID over the full evidence core.

This makes anti-watermark experiments reproducible and auditable without turning the result channel into a cleaned-media export mechanism.

## Design boundary

The project is adversarial, but the core does not implement detector-gradient access, detector-guided mutation selection, adaptive optimization until a detector fails, or a `remove watermark` operation. Mutation implementations receive the artifact and a predefined scenario, not detector feedback. Reports expose robustness failures and assurance changes rather than a derivative selected because attribution was defeated.

This boundary is intentional: fixed hostile attacks can be replayed across implementations and used to improve marking robustness, while adaptive stripping/evasion would instead turn the framework into provenance-bypass tooling.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`docs/ANTI_WATERMARKER.md`](docs/ANTI_WATERMARKER.md), [`docs/C2PA.md`](docs/C2PA.md), [`docs/RECOVERY.md`](docs/RECOVERY.md), [`docs/RESOLVERS.md`](docs/RESOLVERS.md), [`docs/EU_ARTICLE50.md`](docs/EU_ARTICLE50.md), and [`ROADMAP.md`](ROADMAP.md).
