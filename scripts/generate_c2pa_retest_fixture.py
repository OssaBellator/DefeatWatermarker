from __future__ import annotations

import argparse
import json
from pathlib import Path


def _convert_source_to_jpeg(source: Path, output: Path) -> None:
    from PIL import Image

    with Image.open(source) as image:
        rgb = image.convert("RGB")
        try:
            rgb.save(
                output,
                format="JPEG",
                quality=92,
                optimize=False,
                progressive=False,
                subsampling=2,
            )
        finally:
            rgb.close()


def _tamper_jpeg_scan_data(source: Path, output: Path) -> int:
    """Flip one entropy-coded byte while preserving JPEG container structure."""

    data = bytearray(source.read_bytes())
    sos = data.find(b"\xff\xda")
    eoi = data.rfind(b"\xff\xd9")
    if sos < 0 or eoi < 0 or eoi <= sos + 8:
        raise ValueError("signed fixture is not a conventional JPEG")

    segment_length = int.from_bytes(data[sos + 2 : sos + 4], "big")
    scan_start = sos + 2 + segment_length
    if scan_start >= eoi:
        raise ValueError("JPEG scan payload is empty")

    midpoint = scan_start + (eoi - scan_start) // 2
    candidate = None
    for offset in range(0, eoi - scan_start):
        for index in (midpoint + offset, midpoint - offset):
            if not scan_start <= index < eoi:
                continue
            if data[index] not in {0x00, 0xFF}:
                candidate = index
                break
        if candidate is not None:
            break
    if candidate is None:
        raise ValueError("could not locate a safe JPEG scan byte to alter")

    data[candidate] ^= 0x01
    output.write_bytes(data)
    return candidate


def _sign_jpeg(source: Path, output: Path, chain: Path, private_key: Path) -> str:
    from c2pa import Builder, C2paSignerInfo, C2paSigningAlg, Context, Signer

    manifest_json = json.dumps(
        {
            "claim_generator_info": [
                {
                    "name": "DefeatWatermarker fixture generator",
                    "version": "0.1.0",
                }
            ],
            "title": "DefeatWatermarker signed C2PA regression fixture",
            "assertions": [],
        }
    )
    signer_info = C2paSignerInfo(
        alg=C2paSigningAlg.ES256,
        sign_cert=chain.read_bytes(),
        private_key=private_key.read_bytes(),
        ta_url=None,
    )
    with Context() as context:
        with Signer.from_info(signer_info) as signer:
            with Builder(manifest_json, context) as builder:
                with source.open("rb") as src, output.open("w+b") as dest:
                    builder.sign(signer, "image/jpeg", src, dest)
        from c2pa import Reader

        with Reader(str(output), context=context) as reader:
            payload = json.loads(reader.json())
    active = payload.get("active_manifest")
    if not isinstance(active, str) or not active:
        raise RuntimeError("signed fixture did not produce an active C2PA manifest")
    return active


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate signed and tampered C2PA regression fixtures using ephemeral credentials."
    )
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--chain", type=Path, required=True)
    parser.add_argument("--private-key", type=Path, required=True)
    parser.add_argument("--jpeg-source", type=Path, required=True)
    parser.add_argument("--signed", type=Path, required=True)
    parser.add_argument("--tampered", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.jpeg_source.parent.mkdir(parents=True, exist_ok=True)
    args.signed.parent.mkdir(parents=True, exist_ok=True)
    args.tampered.parent.mkdir(parents=True, exist_ok=True)
    args.metadata.parent.mkdir(parents=True, exist_ok=True)

    _convert_source_to_jpeg(args.source, args.jpeg_source)
    active_manifest = _sign_jpeg(
        args.jpeg_source,
        args.signed,
        args.chain,
        args.private_key,
    )
    tampered_offset = _tamper_jpeg_scan_data(args.signed, args.tampered)
    args.metadata.write_text(
        json.dumps(
            {
                "active_manifest": active_manifest,
                "tampered_offset": tampered_offset,
                "source": args.source.name,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
