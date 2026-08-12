from __future__ import annotations

import importlib.util
from pathlib import Path


def pytest_ignore_collect(collection_path: Path, config):  # type: ignore[no-untyped-def]
    """Skip only optional signing tests when cryptography is not installed."""
    return (
        collection_path.name == "test_signatures.py"
        and importlib.util.find_spec("cryptography") is None
    )
