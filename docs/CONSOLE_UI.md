# Guided console UI

`defeat-watermarker-ui` is the human-facing console front end for DefeatWatermarker.

It accepts an artifact, runs the available detector/model adapters, and prints a compact baseline table. For image, audio, video, and text artifacts it can automatically select a built-in fixed anti-watermark attack suite and print the post-attack detector/assurance changes.

## Fast path

```bash
defeat-watermarker-ui path/to/artifact.png
```

The media type is inferred from the file name. For supported modalities, the built-in suite is selected automatically.

The output contains:

- detector/adapter identity;
- watermark/provenance family;
- baseline detected state and confidence;
- verification state and provenance identifier when available;
- per-attack detection survival;
- confidence delta;
- cryptographic-verification survival;
- trust survival;
- provenance-identifier preservation;
- aggregate survival metrics;
- the content-addressed evidence ID.

## Interactive mode

Run the command without an artifact path from an interactive terminal:

```bash
defeat-watermarker-ui
```

The console prompts for the artifact path and infers its media type.

## Save full JSON evidence

```bash
defeat-watermarker-ui artifact.jpg \
  --media-type image/jpeg \
  --json-output .defeat-watermarker/evidence.json
```

The JSON file contains the complete evaluation evidence bundle. It does not contain the source or transformed artifact bytes.

## Scan only

To inspect detector/model outputs without executing an attack suite:

```bash
defeat-watermarker-ui artifact.jpg \
  --scan-only \
  --json-output scan.json
```

Detector-only JSON is also content-addressed. It binds:

- source SHA-256 and byte length, without source bytes;
- media type/modality;
- detector runtime identities;
- exact detector/model results;
- a deterministic `scan_id` over the whole scan core.

Verify it offline:

```bash
defeat-watermarker-scan-verify scan.json
```

Changing a detector confidence, validation state, provenance identifier, runtime identity or source reference after the scan invalidates the `scan_id`.

## Provider detector plugins

Installed read-only detector plugins are discoverable without importing them:

```bash
defeat-watermarker-ui --list-detector-plugins
```

Enable a detector explicitly by entry-point name:

```bash
defeat-watermarker-ui artifact.txt \
  --media-type text/plain \
  --detector-plugin provider-text-v1 \
  --json-output evidence.json
```

The option is repeatable. External detector distribution name/version is included in runtime evidence when Python package metadata can resolve it.

See [`DETECTOR_PLUGINS.md`](DETECTOR_PLUGINS.md) for the plugin boundary. There is intentionally no equivalent external mutation-plugin entry point.

## Custom suite

```bash
defeat-watermarker-ui artifact.jpg \
  --media-type image/jpeg \
  --suite suites/image-platform-v0.1.json
```

A custom suite must pass the same immutable suite validation used by the lower-level CLI.

## Built-in suites

```bash
defeat-watermarker-ui --list-builtins
```

Built-in console suites cover image, PCM-WAV audio, H.264/AAC video, and text normalization/editor workflows. They are carried inside the installed package so the console UI does not depend on a source checkout.

## C2PA trust anchors

```bash
defeat-watermarker-ui asset.jpg \
  --c2pa-trust-anchors ./trust-anchors.pem \
  --json-output evidence.json
```

When the optional C2PA integration is installed, the baseline and post-attack tables include the C2PA verification/trust state.

The UI is intentionally an evidence viewer and fixed attack runner, not a transformed-media exporter. Derivatives stay inside the evaluator and only their hashes, lengths, runtime identities, and detector outcomes are reported.

## Multiple artifacts

For corpus/regression runs, use the bounded batch front end rather than scripting the UI yourself:

```bash
defeat-watermarker-batch ./corpus --output-dir /tmp/dwm-batch
defeat-watermarker-batch-verify /tmp/dwm-batch
```

See [`BATCH.md`](BATCH.md) for bounds, mixed scan/attack behavior and the content-addressed batch layout.
