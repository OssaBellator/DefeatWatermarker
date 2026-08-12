# Permanent retest fixtures

These artifacts are deterministic synthetic inputs for exercising the installed DefeatWatermarker workflows in CI and during local development.

## `example_text.txt`

Generated text containing mixed CRLF line endings, a decomposed Unicode `Café` sequence, trailing horizontal whitespace, punctuation, and a literal `C2PA` string. It is **not** a real watermark or provenance credential.

The built-in `text-editorial-normalization` suite should run all three fixed scenarios (Unicode NFC, LF line endings, trailing-whitespace cleanup) and emit a valid content-addressed evidence document. Batch CI may additionally enable the separately packaged synthetic `fixture-text` detector to exercise the provider-plugin seam.

## `example_image.ppm`

A deterministic 16×16 ASCII PPM gradient/checker image. Its legal PPM comment contains the string `C2PA`, intentionally exercising the conservative `builtin.container-hints.v1` discovery adapter. The comment is a synthetic detector hint only; it is not a signed C2PA manifest.

Expected regression behavior:

1. baseline `builtin.container-hints.v1` detection is true;
2. the built-in image rendition suite decodes the pixels and emits private JPEG derivatives;
3. the PPM comment is not carried into those renditions, so the synthetic container hint is no longer detected;
4. derivative bytes remain private; only hashes/lengths and detector evidence are emitted.

## `example_unknown.bin`

A deterministic opaque file with an unknown/binary modality. It intentionally has no built-in attack suite. In normal batch mode this fixture proves the fallback behavior: known text/image artifacts run their fixed suites, while this artifact produces detector-only scan evidence.

## `README.md`

The fixture documentation itself may be classified as `text/markdown` by the platform MIME table. Batch tests therefore do **not** use it as an unknown-modality fixture; when attack mode is enabled it is valid for the built-in text suite to process it as text.

## Manual retest

```bash
defeat-watermarker-ui fixtures/retests/example_text.txt \
  --media-type text/plain \
  --json-output /tmp/text-evidence.json

defeat-watermarker-ui fixtures/retests/example_image.ppm \
  --media-type image/x-portable-pixmap \
  --json-output /tmp/image-evidence.json

defeat-watermarker evidence verify /tmp/text-evidence.json
defeat-watermarker evidence verify /tmp/image-evidence.json
```

Batch the whole fixture directory:

```bash
defeat-watermarker-batch fixtures/retests \
  --output-dir /tmp/retest-batch

defeat-watermarker-batch-verify /tmp/retest-batch
```

The CI fixture and batch jobs execute these paths on every pull request.
