from defeat_watermarker.capabilities import capability_document
from defeat_watermarker.detector_plugins import DetectorPluginDescriptor


def test_capability_document_has_stable_component_ids() -> None:
    payload = capability_document()
    assert payload["schema_version"] == "0.2"
    ids = [item["component_id"] for item in payload["components"]]
    assert len(ids) == len(set(ids))
    assert "c2pa.reader.v1" in ids
    assert "image.jpeg-reencode.q85.v1" in ids
    assert "audio.wav-pcm16.resample-16khz.v1" in ids
    assert payload["plugin_loading"] == "explicit_opt_in"


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
