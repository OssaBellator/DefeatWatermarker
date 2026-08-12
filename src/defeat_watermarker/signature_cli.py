from __future__ import annotations

import argparse
import json
from pathlib import Path

from .evidence import EvidenceError, load_evidence_document
from .io_utils import atomic_write_text
from .signatures import SignatureError, load_signature, sign_evidence, verify_signature


def _emit(payload: dict[str, object], output: Path | None) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if output is None:
        print(rendered, end="")
    else:
        atomic_write_text(output, rendered)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="defeat-watermarker-signature",
        description="Create and verify detached Ed25519 signatures for verified evidence",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sign = subparsers.add_parser("sign", help="sign a verified evidence ID")
    sign.add_argument("evidence", type=Path)
    sign.add_argument("--private-key", type=Path, required=True)
    sign.add_argument("--key-id", required=True)
    sign.add_argument("--output", type=Path)

    verify = subparsers.add_parser("verify", help="verify evidence and its detached signature")
    verify.add_argument("evidence", type=Path)
    verify.add_argument("signature", type=Path)
    verify.add_argument("--public-key", type=Path, required=True)
    verify.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        evidence = load_evidence_document(args.evidence)
        if args.command == "sign":
            signature = sign_evidence(
                evidence,
                args.private_key,
                key_id=args.key_id,
            )
            _emit(signature.to_dict(), args.output)
            return 0
        if args.command == "verify":
            signature = load_signature(args.signature)
            result = verify_signature(evidence, signature, args.public_key)
            _emit(result.to_dict(), args.output)
            return 0 if result.valid else 8
    except (OSError, UnicodeError, EvidenceError, SignatureError, ValueError) as exc:
        parser.error(str(exc))
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
