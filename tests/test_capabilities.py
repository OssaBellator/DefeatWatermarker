from defeat_watermarker.capabilities import capability_document
from defeat_watermarker.detector_plugins import DetectorPluginDescriptor


def test_capability_document_has_stable_component_ids() -> None:
    payload = capability_document()
    assert payload["schema_version"] == "0.2"
    ids = [item["component_id"] for item in payload["components"]]
    assert len(ids) == len(set(ids))
    assert "c2pa.reader.v1" in ids
    assert "c2pa.manifest-fetch.bounded.v1" in ids
    assert "evidence.signature.ed25519.v1" in ids
    assert "regression.fixed-suite-baseline.v1" in ids
    assert "image.jpeg-reencode.q85.v1" in ids
    assert "audio.wav-pcm16.resample-16khz.v1" in ids
    assert "detector.conformance.read-only.v1" in ids
    assert "evidence.local-test-run.v1" in ids
    assert payload["plugin_loading"] == "explicit_opt_in"


def test_new_local_framework_capabilities_are_available_and_detector_blind() -> None:
    payload = capability_document()
    by_id = {item["component_id"]: item for item in payload["components"]}

    conformance = by_id["detector.conformance.read-only.v1"]
    assert conformance["available"] is True
    assert conformance["component_type"] == "framework"
    assert "without loading mutation logic" in conformance["notes"]

    local_tests = by_id["evidence.local-test-run.v1"]
    assert local_tests["available"] is True
    assert local_tests["component_type"] == "framework"
    assert "source-tree fingerprint" in local_tests["notes"]

    manifest_fetch = by_id["c2pa.manifest-fetch.bounded.v1"]
    assert manifest_fetch["available"] is True
    assert manifest_fetch["component_type"] == "resolver-client"
    assert "no redirects or proxies" in manifest_fetch["notes"]

    regression = by_id["regression.fixed-suite-baseline.v1"]
    assert regression["available"] is True
    assert regression["component_type"] == "regression-gate"
    assert "reported as indeterminate" in regression["notes"]


def test_signature_capability_tracks_optional_dependency(monkeypatch) -> None:
    monkeypatch.setattr(
        "defeat_watermarker.capabilities.importlib.util.find_spec",
        lambda name: None if name == "cryptography" else object(),
    )

    payload = capability_document()
    by_id = {item["component_id"]: item for item in payload["components"]}
    signature = by_id["evidence.signature.ed25519.v1"]

    assert signature["available"] is False
    assert signature["optional_extra"] == "signing"
    assert "private-key bytes are never serialized" in signature["notes"]


def test_capability_document_discovers_plugins_without_loading(monkeypatch) -> None:
    monkeypatch.setattr(
        "defeat_watermarker.capabilities.discover_detector_plugins",
        lambda: (
            DetectorPluginDescriptor(
                name="provider-text",
                value="provider.detector:Adapter",
                distribution="provider-detector",
            ),
        ),
    )

    payload = capability_document()

    assert payload["installed_detector_plugins"] == [
        {
            "name": "provider-text",
            "value": "provider.detector:Adapter",
            "distribution": "provider-detector",
        }
    ]
