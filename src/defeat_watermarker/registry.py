from __future__ import annotations

from collections.abc import Iterable, Iterator

from .adapters.base import WatermarkAdapter


class AdapterRegistry:
    def __init__(self, adapters: Iterable[WatermarkAdapter] = ()) -> None:
        self._adapters: dict[str, WatermarkAdapter] = {}
        for adapter in adapters:
            self.register(adapter)

    def register(self, adapter: WatermarkAdapter) -> None:
        if adapter.adapter_id in self._adapters:
            raise ValueError(f"duplicate adapter_id: {adapter.adapter_id}")
        self._adapters[adapter.adapter_id] = adapter

    def get(self, adapter_id: str) -> WatermarkAdapter:
        try:
            return self._adapters[adapter_id]
        except KeyError as exc:
            raise KeyError(f"unknown adapter_id: {adapter_id}") from exc

    def __iter__(self) -> Iterator[WatermarkAdapter]:
        return iter(self._adapters.values())

    def __len__(self) -> int:
        return len(self._adapters)
