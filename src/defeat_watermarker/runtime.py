from __future__ import annotations

import platform
from importlib import metadata
from typing import Any


def _distribution_version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "unavailable"


def adapter_runtime_identity(adapter: Any) -> tuple[str, ...]:
    """Return bounded, observable implementation/runtime identifiers for an adapter."""

    identity = [
        f"adapter_id={adapter.adapter_id}",
        f"implementation={type(adapter).__module__}.{type(adapter).__qualname__}",
        f"python={platform.python_version()}",
        f"defeat-watermarker={_distribution_version('defeat-watermarker')}",
    ]
    if type(adapter).__module__.startswith("defeat_watermarker.adapters.c2pa"):
        identity.append(f"c2pa-python={_distribution_version('c2pa-python')}")
    return tuple(identity)
