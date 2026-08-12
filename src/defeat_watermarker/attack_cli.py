from __future__ import annotations

import sys

from .cli import main as core_main


def main(argv: list[str] | None = None) -> int:
    """Run the fixed anti-watermark stress workflow.

    This is an adversarial-facing alias for ``defeat-watermarker evaluate``.
    It deliberately inherits the core evaluator's fixed-suite semantics: the
    complete mutation plan is selected before detector results are produced,
    and transformed artifact bytes are not emitted by the command.
    """

    forwarded = list(sys.argv[1:] if argv is None else argv)
    return core_main(["evaluate", *forwarded])


if __name__ == "__main__":
    raise SystemExit(main())
