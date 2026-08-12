# Security and responsible use

DefeatWatermarker is intended for defensive robustness testing of AI provenance systems.

Please do not submit features whose primary purpose is to remove provenance, optimize transformations until a detector fails, expose detector secrets/keys, or export a derivative specifically selected for watermark evasion.

Useful contributions include read-only detectors/verifiers, standards interoperability, fixed robustness test suites, false-positive/false-negative evaluation, provenance recovery, metrics, and CI integration.

## Network and provenance boundaries

The built-in C2PA verifier is local-first: remote-manifest fetching is disabled. Future resolver integrations must be independently bounded and must not silently transmit full artifacts or follow arbitrary provenance URLs. Endpoint policy, timeout/size bounds, and lookup evidence should be explicit.

Reports intentionally omit source and transformed artifact bytes. Provenance graph summaries retain selected textual metadata only and exclude arbitrary assertion payloads and binary resources.

For security-sensitive findings, use GitHub's private vulnerability reporting mechanism when available rather than publishing exploit details in a public issue.
