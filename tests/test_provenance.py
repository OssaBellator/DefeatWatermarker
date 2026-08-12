import pytest

from defeat_watermarker.provenance import ProvenanceGraphError, build_c2pa_provenance_graph


def test_graph_does_not_copy_assertion_payloads_or_thumbnails() -> None:
    label = "contentauth:urn:uuid:test"
    graph = build_c2pa_provenance_graph(
        {
            "active_manifest": label,
            "manifests": {
                label: {
                    "title": "asset.jpg",
                    "format": "image/jpeg",
                    "assertions": [{"data": {"secretish": "do-not-copy"}}],
                    "thumbnail": {"identifier": "resource"},
                    "ingredients": [],
                }
            },
        }
    )
    rendered = repr(graph.to_dict())
    assert "do-not-copy" not in rendered
    assert "thumbnail" not in rendered


def test_graph_rejects_unbounded_manifest_count() -> None:
    manifests = {f"manifest-{index}": {} for index in range(257)}
    with pytest.raises(ProvenanceGraphError, match="exceeds 256 manifests"):
        build_c2pa_provenance_graph({"manifests": manifests})


def test_graph_rejects_non_object_manifest() -> None:
    with pytest.raises(ProvenanceGraphError, match="must be an object"):
        build_c2pa_provenance_graph(
            {"active_manifest": "m", "manifests": {"m": "not-an-object"}}
        )
