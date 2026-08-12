from __future__ import annotations

from dataclasses import dataclass

import pytest

from defeat_watermarker.adapters.base import WatermarkAdapter
from defeat_watermarker.detector_plugins import (
    DetectorPluginError,
    discover_detector_plugins,
    load_detector_plugins,
)
from defeat_watermarker.models import Artifact, DetectionResult, MarkFamily, Modality


class FixtureAdapter(WatermarkAdapter):
    adapter_id = "test.plugin.v1"
    family = MarkFamily.UNKNOWN
    modalities = frozenset({Modality.TEXT})

    def detect(self, artifact: Artifact) -> DetectionResult:
        return DetectionResult(
            adapter_id=self.adapter_id,
            family=self.family,
            detected=True,
            confidence=1.0,
        )


@dataclass
class _FakeDistribution:
    metadata: dict[str, str]


class _FakeEntryPoint:
    def __init__(self, name: str, loaded: object, *, value: str = "fixture:adapter") -> None:
        self.name = name
        self.value = value
        self.dist = _FakeDistribution({"Name": "fixture-distribution"})
        self._loaded = loaded
        self.load_calls = 0

    def load(self) -> object:
        self.load_calls += 1
        return self._loaded


class _FakeEntryPoints(tuple):
    def select(self, *, group: str):
        assert group == "defeat_watermarker.detectors"
        return self


def _install_fake_entry_points(monkeypatch, *items: _FakeEntryPoint) -> None:
    monkeypatch.setattr(
        "defeat_watermarker.detector_plugins.metadata.entry_points",
        lambda: _FakeEntryPoints(items),
    )


def test_discovery_does_not_import_plugin_code(monkeypatch) -> None:
    entry_point = _FakeEntryPoint("fixture-text", FixtureAdapter)
    _install_fake_entry_points(monkeypatch, entry_point)

    descriptors = discover_detector_plugins()

    assert descriptors[0].name == "fixture-text"
    assert descriptors[0].distribution == "fixture-distribution"
    assert entry_point.load_calls == 0


def test_explicit_plugin_name_loads_read_only_adapter(monkeypatch) -> None:
    entry_point = _FakeEntryPoint("fixture-text", FixtureAdapter)
    _install_fake_entry_points(monkeypatch, entry_point)

    adapters = load_detector_plugins(("fixture-text",))

    assert len(adapters) == 1
    assert isinstance(adapters[0], FixtureAdapter)
    assert entry_point.load_calls == 1


def test_unrequested_plugin_is_not_loaded(monkeypatch) -> None:
    entry_point = _FakeEntryPoint("fixture-text", FixtureAdapter)
    _install_fake_entry_points(monkeypatch, entry_point)

    assert load_detector_plugins(()) == ()
    assert entry_point.load_calls == 0


def test_unknown_plugin_is_rejected(monkeypatch) -> None:
    _install_fake_entry_points(monkeypatch)

    with pytest.raises(DetectorPluginError, match="unknown detector plugin"):
        load_detector_plugins(("missing",))


def test_plugin_must_produce_watermark_adapter(monkeypatch) -> None:
    entry_point = _FakeEntryPoint("bad", lambda: object())
    _install_fake_entry_points(monkeypatch, entry_point)

    with pytest.raises(DetectorPluginError, match="WatermarkAdapter"):
        load_detector_plugins(("bad",))


def test_duplicate_plugin_names_are_rejected(monkeypatch) -> None:
    entry_point = _FakeEntryPoint("fixture-text", FixtureAdapter)
    _install_fake_entry_points(monkeypatch, entry_point)

    with pytest.raises(DetectorPluginError, match="must be unique"):
        load_detector_plugins(("fixture-text", "fixture-text"))
