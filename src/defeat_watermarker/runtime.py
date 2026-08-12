from __future__ import annotations

import platform
from importlib import metadata
from typing import Any

_MAX_PLUGIN_DISTRIBUTIONS = 4


def _distribution_version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "unavailable"


def _external_distribution_identities(module_name: str) -> tuple[str, ...]:
    if module_name.startswith("defeat_watermarker"):
        return ()
    top_level = module_name.split(".", 1)[0]
    try:
        distributions = metadata.packages_distributions().get(top_level, [])
    except Exception:
        return ()
    identities: list[str] = []
    for name in sorted(set(distributions))[:_MAX_PLUGIN_DISTRIBUTIONS]:
        identities.append(f"plugin-distribution={name}=={_distribution_version(name)}")
    return tuple(identities)


def adapter_runtime_identity(adapter: Any) -> tuple[str, ...]:
    """Return bounded, observable implementation/runtime identifiers for an adapter."""

    module_name = type(adapter).__module__
    identity = [
        f"adapter_id={adapter.adapter_id}",
        f"implementation={module_name}.{type(adapter).__qualname__}",
        f"python={platform.python_version()}",
        f"defeat-watermarker={_distribution_version('defeat-watermarker')}",
    ]
    if module_name.startswith("defeat_watermarker.adapters.c2pa"):
        identity.append(f"c2pa-python={_distribution_version('c2pa-python')}")
    identity.extend(_external_distribution_identities(module_name))
    return tuple(identity)
