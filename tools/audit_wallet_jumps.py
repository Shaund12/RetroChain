#!/usr/bin/env python3

import argparse
import base64
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class Wallet:
    name: str
    address: str


@dataclass
class BalanceJump:
    height: int
    before_uretro: int
    after_uretro: int
    delta_uretro: int
    txs: List[Dict[str, Any]]


def _http_get_json(url: str, headers: Optional[Dict[str, str]] = None, timeout: float = 10.0) -> Any:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _rest_balance_uretro(rest: str, address: str, height: Optional[int]) -> int:
    headers = {"User-Agent": "retrochain-wallet-audit"}
    if height is not None:
        headers["x-cosmos-block-height"] = str(height)
    o = _http_get_json(f"{rest}/cosmos/bank/v1beta1/balances/{address}", headers=headers, timeout=10.0)
    for b in o.get("balances", []):
        if b.get("denom") == "uretro":
            return int(b.get("amount", "0"))
    return 0


def _rpc_status(rpc: str) -> Dict[str, Any]:
    o = _http_get_json(f"{rpc}/status", headers={"User-Agent": "retrochain-wallet-audit"}, timeout=5.0)
    return o["result"]


def _rpc_block_txs(rpc: str, height: int) -> List[str]:
    o = _http_get_json(
        f"{rpc}/block?{urllib.parse.urlencode({'height': str(height)})}",
        headers={"User-Agent": "retrochain-wallet-audit"},
        timeout=10.0,
    )
    txs = o.get("result", {}).get("block", {}).get("data", {}).get("txs", [])
    return txs or []


def _decode_tx_with_cli(binary: str, tx_b64: str) -> Dict[str, Any]:
    # `tx decode` expects base64 by default.
    out = subprocess.check_output([binary, "tx", "decode", tx_b64, "--output", "json"], text=True)
    return json.loads(out)


def _extract_bank_sends(decoded_tx: Dict[str, Any]) -> List[Dict[str, Any]]:
    msgs = decoded_tx.get("body", {}).get("messages", [])
    sends: List[Dict[str, Any]] = []
    for msg in msgs:
        if msg.get("@type") != "/cosmos.bank.v1beta1.MsgSend":
            continue
        sends.append(
            {
                "type": msg.get("@type"),
                "from": msg.get("from_address"),
                "to": msg.get("to_address"),
                "amount": msg.get("amount"),
            }
        )
    return sends


def _find_next_change_height(
    rest: str,
    address: str,
    start_height: int,
    end_height: int,
    start_bal: int,
) -> Optional[Tuple[int, int]]:
    """Returns (height, new_balance) of first height in (start_height, end_height] where balance != start_bal."""

    # Quick check: if unchanged through end, return None.
    end_bal = _rest_balance_uretro(rest, address, end_height)
    if end_bal == start_bal:
        return None

    lo = start_height
    hi = end_height
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        mid_bal = _rest_balance_uretro(rest, address, mid)
        if mid_bal == start_bal:
            lo = mid
        else:
            hi = mid

    new_bal = _rest_balance_uretro(rest, address, hi)
    return hi, new_bal


def _audit_wallet(
    rest: str,
    rpc: str,
    binary: str,
    wallet: Wallet,
    latest_height: int,
    min_delta_uretro: int,
) -> Tuple[int, int, List[BalanceJump]]:
    genesis_bal = _rest_balance_uretro(rest, wallet.address, 1)
    current_bal = _rest_balance_uretro(rest, wallet.address, None)

    jumps: List[BalanceJump] = []
    cur_h = 1
    cur_bal = genesis_bal

    while cur_h < latest_height:
        found = _find_next_change_height(rest, wallet.address, cur_h, latest_height, cur_bal)
        if not found:
            break
        h, new_bal = found
        before = _rest_balance_uretro(rest, wallet.address, h - 1)
        after = new_bal
        delta = after - before

        if abs(delta) < min_delta_uretro:
            cur_h = h
            cur_bal = after
            continue

        txs_b64 = _rpc_block_txs(rpc, h)
        tx_details: List[Dict[str, Any]] = []
        for tx_b64 in txs_b64:
            try:
                decoded = _decode_tx_with_cli(binary, tx_b64)
            except Exception as e:
                tx_details.append({"decode_error": str(e)})
                continue
            sends = _extract_bank_sends(decoded)
            # Keep only sends involving this wallet.
            rel = [s for s in sends if s.get("from") == wallet.address or s.get("to") == wallet.address]
            if rel:
                tx_details.append({"bank_sends": rel})

        jumps.append(
            BalanceJump(
                height=h,
                before_uretro=before,
                after_uretro=after,
                delta_uretro=delta,
                txs=tx_details,
            )
        )

        cur_h = h
        cur_bal = after

    return genesis_bal, current_bal, jumps


def _fmt_retro(uretro: int) -> str:
    return f"{uretro / 1_000_000:.6f}"


def main() -> int:
    p = argparse.ArgumentParser(description="Audit genesis balances and later balance jumps for key wallets.")
    p.add_argument("--rpc", default=os.environ.get("RETROCHAIN_RPC", "http://127.0.0.1:26657"))
    p.add_argument("--rest", default=os.environ.get("RETROCHAIN_REST", "http://127.0.0.1:1317"))
    p.add_argument("--binary", default=os.environ.get("RETROCHAIN_BIN", "retrochaind"))
    p.add_argument("--min-delta-uretro", type=int, default=1, help="Ignore balance changes smaller than this.")
    p.add_argument("--max-height", type=int, default=0, help="Override latest height (0 = use RPC status).")

    args = p.parse_args()

    status = _rpc_status(args.rpc)
    latest_height = int(status["sync_info"]["latest_block_height"])
    if args.max_height and args.max_height > 0:
        latest_height = min(latest_height, args.max_height)

    wallets = [
        Wallet("foundation_validator", "cosmos1fscvf7rphx477z6vd4sxsusm2u8a70kewvc8wy"),
        Wallet("ecosystem_rewards", "cosmos1exqr633rjzls2h4txrpu0cxhnxx0dquylf074x"),
        Wallet("liquidity_fund", "cosmos1w506apt4kyq72xgaakwxrvak8w5d94upn3gdf3"),
        Wallet("community_fund", "cosmos1tksjh4tkdjfnwkkwty0wyuy4pv93q5q4lepgrn"),
        Wallet("dev_fund", "cosmos1epy8qnuu00w76xvvlt2mc7q8qslhw206vzu5vs"),
        Wallet("shaun_profit", "cosmos1us0jjdd5dj0v499g959jatpnh6xuamwhwdrrgq"),
        Wallet("kitty_charity", "cosmos1ydn44ufvhddqhxu88m709k46hdm0dfjwm8v0tt"),
    ]

    print(f"RPC: {args.rpc}")
    print(f"REST: {args.rest}")
    print(f"Latest height: {latest_height}")
    print()

    for w in wallets:
        g, cur, jumps = _audit_wallet(
            rest=args.rest,
            rpc=args.rpc,
            binary=args.binary,
            wallet=w,
            latest_height=latest_height,
            min_delta_uretro=args.min_delta_uretro,
        )
        print(f"== {w.name} ==")
        print(f"address: {w.address}")
        print(f"genesis@1: {g} uretro ({_fmt_retro(g)} RETRO)")
        print(f"current:   {cur} uretro ({_fmt_retro(cur)} RETRO)")
        if not jumps:
            print("jumps: (none)")
            print()
            continue
        print("jumps:")
        for j in jumps:
            sign = "+" if j.delta_uretro >= 0 else ""
            print(
                f"- height {j.height}: {j.before_uretro} -> {j.after_uretro} ({sign}{j.delta_uretro} uretro, {sign}{_fmt_retro(j.delta_uretro)} RETRO)"
            )
            if not j.txs:
                continue
            for td in j.txs:
                if "bank_sends" in td:
                    for s in td["bank_sends"]:
                        print(f"  - MsgSend {s['from']} -> {s['to']} amount={s['amount']}")
                elif "decode_error" in td:
                    print(f"  - (decode error) {td['decode_error']}")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
