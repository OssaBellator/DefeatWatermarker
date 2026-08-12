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

To inspect the detector/model outputs without executing an attack suite:

```bash
defeat-watermarker-ui artifact.jpg --scan-only
```

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

The UI is intentionally an evidence viewer and attack runner, not a transformed-media exporter. Derivatives stay inside the evaluator and only their hashes, lengths, runtime identities, and detector outcomes are reported.
