from __future__ import annotations

import re
from dataclasses import dataclass
from importlib import metadata
from typing import Any, Iterable

from .adapters.base import WatermarkAdapter

_ENTRY_POINT_GROUP = "defeat_watermarker.detectors"
_PLUGIN_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


class DetectorPluginError(ValueError):
    """Raised when an explicitly requested detector plugin cannot be loaded safely."""


@dataclass(frozen=True, slots=True)
class DetectorPluginDescriptor:
    name: str
    value: str
    distribution: str | None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "name": self.name,
            "value": self.value,
            "distribution": self.distribution,
        }


def _detector_entry_points() -> tuple[metadata.EntryPoint, ...]:
    discovered = metadata.entry_points()
    selected = discovered.select(group=_ENTRY_POINT_GROUP)
    return tuple(sorted(selected, key=lambda item: item.name))


def discover_detector_plugins() -> tuple[DetectorPluginDescriptor, ...]:
    descriptors: list[DetectorPluginDescriptor] = []
    for entry_point in _detector_entry_points():
        distribution = None
        if entry_point.dist is not None:
            distribution = entry_point.dist.metadata.get("Name")
        descriptors.append(
            DetectorPluginDescriptor(
                name=entry_point.name,
                value=entry_point.value,
                distribution=distribution,
            )
        )
    return tuple(descriptors)


def _coerce_adapter(value: Any, *, plugin_name: str) -> WatermarkAdapter:
    candidate = value
    if isinstance(candidate, type) and issubclass(candidate, WatermarkAdapter):
        candidate = candidate()
    elif not isinstance(candidate, WatermarkAdapter) and callable(candidate):
        candidate = candidate()

    if not isinstance(candidate, WatermarkAdapter):
        raise DetectorPluginError(
            f"detector plugin {plugin_name!r} did not produce a WatermarkAdapter"
        )
    if not candidate.adapter_id or len(candidate.adapter_id) > 128:
        raise DetectorPluginError(
            f"detector plugin {plugin_name!r} produced an invalid adapter_id"
        )
    return candidate


def load_detector_plugins(names: Iterable[str]) -> tuple[WatermarkAdapter, ...]:
    requested = tuple(names)
    if len(requested) != len(set(requested)):
        raise DetectorPluginError("detector plugin names must be unique")
    for name in requested:
        if not _PLUGIN_NAME_RE.fullmatch(name):
            raise DetectorPluginError(f"invalid detector plugin name: {name!r}")

    available = {item.name: item for item in _detector_entry_points()}
    adapters: list[WatermarkAdapter] = []
    seen_adapter_ids: set[str] = set()
    for name in requested:
        entry_point = available.get(name)
        if entry_point is None:
            raise DetectorPluginError(f"unknown detector plugin: {name}")
        try:
            loaded = entry_point.load()
            adapter = _coerce_adapter(loaded, plugin_name=name)
        except DetectorPluginError:
            raise
        except Exception as exc:
            raise DetectorPluginError(
                f"detector plugin {name!r} failed to load: {exc}"
            ) from exc
        if adapter.adapter_id in seen_adapter_ids:
            raise DetectorPluginError(
                f"detector plugins produced duplicate adapter_id: {adapter.adapter_id}"
            )
        seen_adapter_ids.add(adapter.adapter_id)
        adapters.append(adapter)
    return tuple(adapters)
