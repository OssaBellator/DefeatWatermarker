# Permanent retest fixtures

These artifacts are deterministic synthetic inputs for exercising the installed `defeat-watermarker-ui` workflow in CI and during local development.

## `example_text.txt`

Generated text containing mixed CRLF line endings, a decomposed Unicode `Café` sequence, trailing horizontal whitespace, punctuation, and a literal `C2PA` string. It is **not** a real watermark or provenance credential.

The built-in `text-editorial-normalization` suite should run all three fixed scenarios (Unicode NFC, LF line endings, trailing-whitespace cleanup) and emit a valid content-addressed evidence document.

## `example_image.ppm`

A deterministic 16×16 ASCII PPM gradient/checker image. Its legal PPM comment contains the string `C2PA`, intentionally exercising the conservative `builtin.container-hints` discovery adapter. The comment is a synthetic detector hint only; it is not a signed C2PA manifest.

Expected regression behavior:

1. baseline `builtin.container-hints` detection is true;
2. the built-in image rendition suite decodes the pixels and emits private JPEG derivatives;
3. the PPM comment is not carried into those renditions, so the synthetic container hint is no longer detected;
4. derivative bytes remain private; only hashes/lengths and detector evidence are emitted.

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

The CI fixture-retest job executes the same paths on every pull request.
