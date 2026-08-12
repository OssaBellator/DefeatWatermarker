# EU AI Act Article 50 engineering profile

The repository ships a versioned **engineering-readiness** profile for provider-side marking under Article 50(2). It is intentionally not a legal compliance checker.

The profile reflects the technical dimensions stated in Article 50(2) and the Commission's 2026 guidance/code: synthetic audio, image, video and text outputs are within the provider marking obligation when the provision applies; marking is machine-readable and detectable; and technical solutions are expected to be effective, interoperable, robust and reliable as far as technically feasible.

DefeatWatermarker can test some of those dimensions directly and records the others as explicit gaps rather than inferring compliance.

## Profile assessment

```bash
python -m defeat_watermarker profile validate \
  profiles/eu-article50-provider-marking-v0.1.json

python -m defeat_watermarker profile assess \
  profiles/eu-article50-provider-marking-v0.1.json \
  --suite suites/image-platform-v0.1.json
```

An assessment checks:

- required framework capabilities by stable capability ID;
- fixed-suite scenario coverage for each required modality;
- the exact profile digest and supplied suite digests.

The initial profile deliberately requires interoperability and false-positive/false-negative reliability capabilities that are not implemented yet. Therefore the repository should report an engineering gap today rather than manufacture a green compliance-looking result.

## Legal scope remains external

The tool does not decide whether a particular system/output is legally in scope, whether an exemption applies, what is technically feasible for a provider, whether an organisation can rely on the Code of Practice, or whether a competent authority would consider the provider compliant. Those determinations depend on the Regulation, Commission guidance/code, facts and applicable enforcement context.
