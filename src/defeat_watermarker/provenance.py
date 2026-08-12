from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .digests import sha256_bytes

_MAX_MANIFESTS = 256
_MAX_INGREDIENTS_PER_MANIFEST = 512
_MAX_TEXT = 2048


class ProvenanceGraphError(ValueError):
    """Raised when provenance metadata is malformed or exceeds graph bounds."""


class ProvenanceNodeKind(str, Enum):
    ASSET = "asset"
    MANIFEST = "manifest"
    INGREDIENT = "ingredient"


@dataclass(frozen=True, slots=True)
class ProvenanceNode:
    node_id: str
    kind: ProvenanceNodeKind
    metadata: tuple[tuple[str, str], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "kind": self.kind.value,
            "metadata": {key: value for key, value in self.metadata},
        }


@dataclass(frozen=True, slots=True)
class ProvenanceEdge:
    source: str
    target: str
    relation: str

    def to_dict(self) -> dict[str, str]:
        return {"source": self.source, "target": self.target, "relation": self.relation}


@dataclass(frozen=True, slots=True)
class ProvenanceGraph:
    nodes: tuple[ProvenanceNode, ...]
    edges: tuple[ProvenanceEdge, ...]
    active_manifest_node: str | None = None
    schema_version: str = "0.1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "active_manifest_node": self.active_manifest_node,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
        }


def _bounded_text(value: Any, *, noun: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ProvenanceGraphError(f"{noun} must be a string")
    if len(value) > _MAX_TEXT:
        raise ProvenanceGraphError(f"{noun} exceeds {_MAX_TEXT} characters")
    return value


def _node_id(prefix: str, seed: str) -> str:
    return f"{prefix}:{sha256_bytes(seed.encode('utf-8'))[:24]}"


def _metadata(**values: str | None) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((key, value) for key, value in values.items() if value is not None))


def build_c2pa_provenance_graph(manifest_store: dict[str, Any]) -> ProvenanceGraph:
    """Build a bounded graph from the public C2PA Reader JSON representation.

    Only selected textual provenance fields are retained. Binary resources, assertion payloads,
    thumbnails, and arbitrary manifest data are deliberately excluded from the graph.
    """

    if not isinstance(manifest_store, dict):
        raise ProvenanceGraphError("manifest store must be an object")
    manifests = manifest_store.get("manifests", {})
    if not isinstance(manifests, dict):
        raise ProvenanceGraphError("manifests must be an object")
    if len(manifests) > _MAX_MANIFESTS:
        raise ProvenanceGraphError(f"manifest store exceeds {_MAX_MANIFESTS} manifests")

    active_label = _bounded_text(manifest_store.get("active_manifest"), noun="active_manifest")
    nodes: list[ProvenanceNode] = [
        ProvenanceNode(node_id="asset", kind=ProvenanceNodeKind.ASSET)
    ]
    edges: list[ProvenanceEdge] = []
    manifest_nodes: dict[str, str] = {}

    for raw_label, raw_manifest in manifests.items():
        label = _bounded_text(raw_label, noun="manifest label")
        if label is None:
            raise ProvenanceGraphError("manifest label cannot be null")
        if not isinstance(raw_manifest, dict):
            raise ProvenanceGraphError(f"manifest {label!r} must be an object")
        node_id = _node_id("manifest", label)
        manifest_nodes[label] = node_id
        signature = raw_manifest.get("signature_info", {})
        if signature is None:
            signature = {}
        if not isinstance(signature, dict):
            raise ProvenanceGraphError(f"manifest {label!r} signature_info must be an object")
        nodes.append(
            ProvenanceNode(
                node_id=node_id,
                kind=ProvenanceNodeKind.MANIFEST,
                metadata=_metadata(
                    label=label,
                    title=_bounded_text(raw_manifest.get("title"), noun="manifest title"),
                    media_type=_bounded_text(raw_manifest.get("format"), noun="manifest format"),
                    instance_id=_bounded_text(
                        raw_manifest.get("instance_id"), noun="manifest instance_id"
                    ),
                    claim_generator=_bounded_text(
                        raw_manifest.get("claim_generator"), noun="claim_generator"
                    ),
                    issuer=_bounded_text(signature.get("issuer"), noun="signature issuer"),
                    common_name=_bounded_text(
                        signature.get("common_name"), noun="signature common_name"
                    ),
                ),
            )
        )
        edges.append(
            ProvenanceEdge(
                source="asset",
                target=node_id,
                relation="active_manifest" if label == active_label else "manifest",
            )
        )

    for raw_label, raw_manifest in manifests.items():
        label = str(raw_label)
        manifest_node = manifest_nodes[label]
        ingredients = raw_manifest.get("ingredients", [])
        if ingredients is None:
            ingredients = []
        if not isinstance(ingredients, list):
            raise ProvenanceGraphError(f"manifest {label!r} ingredients must be an array")
        if len(ingredients) > _MAX_INGREDIENTS_PER_MANIFEST:
            raise ProvenanceGraphError(
                f"manifest {label!r} exceeds {_MAX_INGREDIENTS_PER_MANIFEST} ingredients"
            )

        for index, ingredient in enumerate(ingredients):
            if not isinstance(ingredient, dict):
                raise ProvenanceGraphError(
                    f"manifest {label!r} ingredient {index} must be an object"
                )
            seed = f"{label}\x00{index}\x00{ingredient.get('instance_id', '')}"
            ingredient_node = _node_id("ingredient", seed)
            nodes.append(
                ProvenanceNode(
                    node_id=ingredient_node,
                    kind=ProvenanceNodeKind.INGREDIENT,
                    metadata=_metadata(
                        title=_bounded_text(ingredient.get("title"), noun="ingredient title"),
                        media_type=_bounded_text(
                            ingredient.get("format"), noun="ingredient format"
                        ),
                        instance_id=_bounded_text(
                            ingredient.get("instance_id"), noun="ingredient instance_id"
                        ),
                        document_id=_bounded_text(
                            ingredient.get("document_id"), noun="ingredient document_id"
                        ),
                        relationship=_bounded_text(
                            ingredient.get("relationship"), noun="ingredient relationship"
                        ),
                    ),
                )
            )
            edges.append(
                ProvenanceEdge(source=manifest_node, target=ingredient_node, relation="ingredient")
            )

            ingredient_manifest = ingredient.get("active_manifest")
            if isinstance(ingredient_manifest, str) and ingredient_manifest in manifest_nodes:
                edges.append(
                    ProvenanceEdge(
                        source=ingredient_node,
                        target=manifest_nodes[ingredient_manifest],
                        relation="ingredient_manifest",
                    )
                )

    return ProvenanceGraph(
        nodes=tuple(nodes),
        edges=tuple(edges),
        active_manifest_node=manifest_nodes.get(active_label) if active_label is not None else None,
    )
