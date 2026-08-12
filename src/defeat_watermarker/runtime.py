from __future__ import annotations

import platform
from importlib import metadata
from typing import Any

_MAX_PLUGIN_DISTRIBUTIONS = 4
_MAX_ADAPTER_RUNTIME_ITEMS = 8
_MAX_ADAPTER_RUNTIME_ITEM_LENGTH = 256


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


def _adapter_supplied_runtime_identity(adapter: Any) -> tuple[str, ...]:
    hook = getattr(adapter, "runtime_identity", None)
    if hook is None:
        return ()
    if not callable(hook):
        raise ValueError("adapter runtime_identity must be callable")
    try:
        values = tuple(hook())
    except Exception as exc:
        raise ValueError("adapter runtime_identity failed") from exc
    if len(values) > _MAX_ADAPTER_RUNTIME_ITEMS:
        raise ValueError(
            f"adapter runtime_identity exceeds {_MAX_ADAPTER_RUNTIME_ITEMS} entries"
        )
    output: list[str] = []
    for item in values:
        if (
            not isinstance(item, str)
            or not item
            or len(item) > _MAX_ADAPTER_RUNTIME_ITEM_LENGTH
            or "\n" in item
            or "\r" in item
        ):
            raise ValueError("adapter runtime_identity contains invalid identity data")
        output.append(f"adapter-runtime={item}")
    return tuple(output)


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
    identity.extend(_adapter_supplied_runtime_identity(adapter))
    return tuple(identity)
