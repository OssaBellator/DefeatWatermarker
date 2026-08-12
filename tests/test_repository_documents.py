from __future__ import annotations

import json
from pathlib import Path

from defeat_watermarker.profiles import load_profile
from defeat_watermarker.reliability import load_corpus
from defeat_watermarker.suites import load_suite


ROOT = Path(__file__).resolve().parents[1]


def test_every_checked_in_robustness_suite_loads() -> None:
    paths = sorted((ROOT / "suites").glob("*.json"))
    assert paths
    digests: set[str] = set()
    for path in paths:
        suite = load_suite(path)
        assert suite.digest not in digests
        digests.add(suite.digest)


def test_every_checked_in_engineering_profile_loads() -> None:
    paths = sorted((ROOT / "profiles").glob("*.json"))
    assert paths
    for path in paths:
        profile = load_profile(path)
        assert len(profile.digest) == 64


def test_every_checked_in_reliability_corpus_loads() -> None:
    paths = sorted((ROOT / "benchmarks" / "reliability").glob("*/corpus.json"))
    assert paths
    for path in paths:
        corpus = load_corpus(path)
        assert len(corpus.digest) == 64


def test_every_checked_in_schema_is_valid_json() -> None:
    paths = sorted((ROOT / "schemas").glob("*.schema.json"))
    assert paths
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["$schema"] == "https://json-schema.org/draft/2020-12/schema"
