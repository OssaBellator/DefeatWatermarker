# Anti-watermark red-team model

DefeatWatermarker is intentionally an **anti-watermark red-team harness**: its job is to challenge watermark and provenance mechanisms and produce evidence about where they fail.

The adversarial workflow is:

```text
reviewed attack suite
        ↓
complete mutation plan fixed before detection
        ↓
source artifact → baseline detectors
        ↓
fixed hostile/real-world transformations
        ↓
post-transform detectors
        ↓
robustness + assurance failure evidence
```

The term *anti-watermarker* therefore refers to the side of the evaluation the tool represents: it is the adversary attacking watermark durability, not a watermark generator.

## Attack workflow

The installed `defeat-watermarker-attack` command is an explicit adversarial alias for the fixed evaluator:

```bash
defeat-watermarker-attack asset.jpg \
  --media-type image/jpeg \
  --suite suites/image-platform-v0.1.json \
  --output evidence.json
```

The command executes the same reviewed, versioned mutation suite as `defeat-watermarker evaluate`. The suite is selected before detector results exist. This makes attack runs reproducible and prevents the experiment from silently changing in response to a detector score.

The checked-in suites already cover attack surfaces such as repeated image recompression, resize/crop, audio level/downmix/resampling, text normalization/editor cleanup, and video scale/transcode. New hostile-but-reproducible processing families can be added as reviewed mutation implementations and immutable suite entries.

## Evidence produced by an attack

An attack run records which detector signals survived, confidence changes, cryptographic-verification survival, trust survival, provenance-identifier continuity, derivative hashes and runtime identities. Transformed artifact bytes are deliberately not part of the evidence bundle.

This makes the useful output of the anti-watermarker a statement such as:

```text
C2PA remained detectable after the attack,
but cryptographic validity failed after scenario X.
```

or:

```text
perceptual mark detection fell from 0.98 to 0.31
under the fixed three-generation rendition suite.
```

rather than an opaque claim that a watermark was "removed".

## Boundary

The project can model increasingly hostile fixed transformations, multi-generation processing, partial-content edits, platform renditions, interoperability failures and future watermark families. It does not turn detector feedback into an optimizer that searches for the smallest transformation that defeats a watermark, expose detector gradients/secret material, or emit a derivative selected specifically because provenance detection failed.

Keeping that boundary preserves the scientific value of the attack result: the same immutable attack can be replayed across watermark versions, vendors, model releases and regulatory test profiles without the test itself adapting to the implementation under test.
