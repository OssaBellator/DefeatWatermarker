from __future__ import annotations

import defeat_watermarker.attack_cli as attack_cli


def test_attack_cli_delegates_to_fixed_evaluator(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_core_main(argv: list[str]) -> int:
        calls.append(argv)
        return 7

    monkeypatch.setattr(attack_cli, "core_main", fake_core_main)

    result = attack_cli.main(
        ["asset.jpg", "--suite", "suites/image-platform-v0.1.json", "--media-type", "image/jpeg"]
    )

    assert result == 7
    assert calls == [
        [
            "evaluate",
            "asset.jpg",
            "--suite",
            "suites/image-platform-v0.1.json",
            "--media-type",
            "image/jpeg",
        ]
    ]
