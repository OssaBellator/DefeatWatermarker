# Suite capability preflight

A robustness suite should fail before artifact processing when its declared transformations cannot run in the current environment.

```bash
python -m defeat_watermarker.preflight_cli suites/video-platform-v0.1.json
```

The preflight report binds the exact suite digest and current machine-readable capability document digest. Each scenario is classified as known/runnable or a gap. Exit code `9` means at least one mutation is unknown or unavailable.

This matters for optional dependencies such as Pillow and FFmpeg: merely checking a suite file into the repository does not count as runnable modality coverage. The same availability rule is used by the Article 50 engineering-profile assessment.

Preflight never reads the source artifact and never runs a detector or mutation. It is therefore suitable as an early CI/configuration check before protected or large media enters the evaluation process.
