from defeat_watermarker.capabilities import capability_document


def test_capability_document_has_stable_component_ids() -> None:
    payload = capability_document()
    assert payload["schema_version"] == "0.1"
    ids = [item["component_id"] for item in payload["components"]]
    assert len(ids) == len(set(ids))
    assert "c2pa.reader.v1" in ids
    assert "image.jpeg-reencode.q85.v1" in ids
