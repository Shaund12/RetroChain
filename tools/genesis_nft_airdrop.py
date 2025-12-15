#!/usr/bin/env python3
"""Generate `app_state.nft` genesis JSON for a native x/nft airdrop.

RetroChain includes `x/nft`, but (in the current module wiring) there is no tx
for issuing classes or minting NFTs. So to pre-mint native NFTs you must add
them to genesis.

This script outputs a JSON object suitable to place at `app_state.nft`.

Example:
  python3 tools/genesis_nft_airdrop.py \
    --class-id retro-genesis-2025 \
    --class-name "RetroChain Genesis" \
    --class-symbol GENESIS \
    --class-description "Genesis NFT for early wallets" \
    --class-uri "ipfs://.../class.json" \
    --token-uri "ipfs://.../nft.json" \
    --owner cosmos1... --owner cosmos1...
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class ClassSpec:
    class_id: str
    name: str
    symbol: str
    description: str
    uri: str
    uri_hash: str


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate app_state.nft genesis JSON")
    p.add_argument("--class-id", required=True)
    p.add_argument("--class-name", required=True)
    p.add_argument("--class-symbol", required=True)
    p.add_argument("--class-description", required=True)
    p.add_argument("--class-uri", required=True)
    p.add_argument("--class-uri-hash", default="")

    p.add_argument(
        "--token-uri",
        default=None,
        help="URI for each NFT. Defaults to class-uri if not provided.",
    )
    p.add_argument("--token-uri-hash", default="")

    p.add_argument(
        "--owner",
        action="append",
        default=[],
        help="Owner address (repeatable). If none provided, read newline-separated owners from stdin.",
    )

    p.add_argument(
        "--id-prefix",
        default="genesis-",
        help="NFT id prefix (default: genesis-).",
    )
    p.add_argument(
        "--start",
        type=int,
        default=1,
        help="Starting sequence number for NFT ids (default: 1).",
    )
    p.add_argument(
        "--width",
        type=int,
        default=4,
        help="Zero-padding width for the sequence (default: 4).",
    )
    p.add_argument("--pretty", action="store_true", help="Pretty-print JSON")

    return p.parse_args(argv)


def _read_owners(args: argparse.Namespace) -> list[str]:
    owners = [o.strip() for o in (args.owner or []) if o.strip()]
    if owners:
        return owners

    data = sys.stdin.read()
    owners = []
    for line in data.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        owners.append(line)
    return owners


def _make_genesis(class_spec: ClassSpec, owners: list[str], token_uri: str, token_uri_hash: str, id_prefix: str, start: int, width: int) -> dict:
    if not owners:
        raise SystemExit("No owners provided. Use --owner or provide owners via stdin.")

    classes = [
        {
            "id": class_spec.class_id,
            "name": class_spec.name,
            "symbol": class_spec.symbol,
            "description": class_spec.description,
            "uri": class_spec.uri,
            "uri_hash": class_spec.uri_hash,
            "data": None,
        }
    ]

    entries = []
    for i, owner in enumerate(owners, start=start):
        nft_id = f"{id_prefix}{i:0{width}d}"
        entries.append(
            {
                "owner": owner,
                "nfts": [
                    {
                        "class_id": class_spec.class_id,
                        "id": nft_id,
                        "uri": token_uri,
                        "uri_hash": token_uri_hash,
                        "data": None,
                    }
                ],
            }
        )

    return {"classes": classes, "entries": entries}


def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    owners = _read_owners(args)

    class_spec = ClassSpec(
        class_id=args.class_id,
        name=args.class_name,
        symbol=args.class_symbol,
        description=args.class_description,
        uri=args.class_uri,
        uri_hash=args.class_uri_hash,
    )

    token_uri = args.token_uri if args.token_uri is not None else class_spec.uri

    obj = _make_genesis(
        class_spec=class_spec,
        owners=owners,
        token_uri=token_uri,
        token_uri_hash=args.token_uri_hash,
        id_prefix=args.id_prefix,
        start=args.start,
        width=args.width,
    )

    if args.pretty:
        json.dump(obj, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        json.dump(obj, sys.stdout, ensure_ascii=False, separators=(",", ":"))
        sys.stdout.write("\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
