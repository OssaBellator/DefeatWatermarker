from __future__ import annotations

import argparse
import json
from pathlib import Path

from .evidence import EvidenceError, load_evidence_document
from .io_utils import atomic_write_text
from .signatures import SignatureError, load_signature, sign_evidence, verify_signature


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="defeat-watermarker-evidence-signature",
        description=(
            "Create or verify detached Ed25519 signatures over verified "
            "evaluation evidence."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sign = sub.add_parser("sign", help="sign a verified evaluation evidence document")
    sign.add_argument("evidence", type=Path)
    sign.add_argument("--private-key", type=Path, required=True)
    sign.add_argument("--key-id", required=True)
    sign.add_argument("--output", type=Path, required=True)

    verify = sub.add_parser("verify", help="verify a detached evidence signature")
    verify.add_argument("evidence", type=Path)
    verify.add_argument("signature", type=Path)
    verify.add_argument("--public-key", type=Path, required=True)
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
            atomic_write_text(
                args.output,
                json.dumps(signature.to_dict(), indent=2, sort_keys=True) + "\n",
            )
            print(f"Signature: {args.output}")
            print(f"Signature ID: {signature.signature_id}")
            return 0

        signature = load_signature(args.signature)
        result = verify_signature(evidence, signature, args.public_key)
    except (OSError, UnicodeError, EvidenceError, SignatureError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0 if result.valid else 4


if __name__ == "__main__":
    raise SystemExit(main())
