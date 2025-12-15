#!/usr/bin/env python3
"""Derive a list of "early wallets" from the SQLite indexer DB.

Definition (simple + deterministic):
- Any bech32 account address matching `cosmos1...` that appears anywhere in
  `events.attributes_json` at heights <= N.

This is intentionally conservative and does not attempt to fully understand
all Cosmos event schemas.

Usage:
  python3 tools/eligible_wallets_before_height.py --db ~/.retrochain/indexer.sqlite --max-height 1000000 > owners.txt

Notes:
- Requires the indexer DB produced by `tools/sql_indexer.py`.
- If you want a different eligibility rule (e.g., "has non-zero balance"), this
  will need a different data source.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from typing import Iterable


ADDR_RE = re.compile(r"\bcosmos1[0-9a-z]{20,80}\b")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="List wallets seen on-chain up to a given height")
    p.add_argument("--db", default=os.path.expanduser("~/.retrochain/indexer.sqlite"), help="Path to indexer sqlite DB")
    p.add_argument("--max-height", type=int, required=True, help="Include events with height <= this value")
    p.add_argument("--min-height", type=int, default=1, help="Include events with height >= this value")
    p.add_argument("--exclude", action="append", default=[], help="Exclude an address (repeatable)")
    p.add_argument("--include-valoper", action="store_true", help="Also include cosmosvaloper1... addrs (default off)")
    p.add_argument("--format", choices=["txt", "json"], default="txt")
    return p.parse_args(argv)


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def _extract_addrs_from_attributes_json(attributes_json: str, include_valoper: bool) -> set[str]:
    out: set[str] = set()
    if not attributes_json:
        return out

    # Fast-path: regex scan the raw json string.
    for m in ADDR_RE.finditer(attributes_json):
        out.add(m.group(0))

    if include_valoper:
        for m in re.finditer(r"\bcosmosvaloper1[0-9a-z]{20,80}\b", attributes_json):
            out.add(m.group(0))

    return out


def iter_event_attribute_json(conn: sqlite3.Connection, min_h: int, max_h: int, batch: int = 10_000) -> Iterable[str]:
    offset = 0
    while True:
        rows = conn.execute(
            "SELECT attributes_json FROM events WHERE height >= ? AND height <= ? ORDER BY id ASC LIMIT ? OFFSET ?",
            (int(min_h), int(max_h), int(batch), int(offset)),
        ).fetchall()
        if not rows:
            return
        for r in rows:
            yield str(r["attributes_json"])
        offset += len(rows)


def main(argv: list[str]) -> int:
    args = _parse_args(argv)

    db_path = os.path.expanduser(args.db)
    if not os.path.isfile(db_path):
        print(f"DB not found: {db_path}", file=sys.stderr)
        return 2

    if args.min_height < 1 or args.max_height < 1 or args.min_height > args.max_height:
        print("Invalid height range", file=sys.stderr)
        return 2

    exclude = {e.strip() for e in (args.exclude or []) if e.strip()}

    addrs: set[str] = set()
    with _connect(db_path) as conn:
        for attrs_json in iter_event_attribute_json(conn, args.min_height, args.max_height):
            addrs |= _extract_addrs_from_attributes_json(attrs_json, include_valoper=bool(args.include_valoper))

    if exclude:
        addrs = {a for a in addrs if a not in exclude}

    # Stable output
    items = sorted(addrs)

    if args.format == "json":
        json.dump(items, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0

    for a in items:
        sys.stdout.write(a + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
