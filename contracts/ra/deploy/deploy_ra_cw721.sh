#!/usr/bin/env bash
set -euo pipefail

# Deploy a CW721 (NFT) contract (ra_cw721) to RetroChain (CosmWasm).
#
# Usage:
#   KEY=foundation_validator RPC=http://localhost:26657 CHAIN_ID=retrochain-mainnet \
#     ./contracts/ra/deploy/deploy_ra_cw721.sh
#
# Optional env:
#   HOME_DIR=~/.retrochain
#   FEES=5000uretro
#   GAS=auto
#   GAS_ADJUSTMENT=1.3
#   WASM_PATH=... (defaults to target/wasm32-unknown-unknown/release/ra_cw721.wasm)
#   INSTANTIATE_MSG=... (defaults to contracts/ra/deploy/instantiate_ra_cw721.json)
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CONTRACTS_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

KEY="${KEY:-foundation_validator}"
KEYRING_BACKEND="${KEYRING_BACKEND:-os}"
RPC="${RPC:-http://localhost:26657}"
CHAIN_ID="${CHAIN_ID:-retrochain-mainnet}"
HOME_DIR="${HOME_DIR:-$HOME/.retrochain}"
FEES="${FEES:-5000uretro}"
GAS="${GAS:-auto}"
GAS_ADJUSTMENT="${GAS_ADJUSTMENT:-1.3}"

WASM_PATH="${WASM_PATH:-$CONTRACTS_ROOT/target/wasm32-unknown-unknown/release/ra_cw721.wasm}"
INSTANTIATE_MSG="${INSTANTIATE_MSG:-$CONTRACTS_ROOT/deploy/instantiate_ra_cw721.json}"

# Some wasm runtimes reject bulk-memory ops (memory.copy/fill). If your chain's
# VM is compiled without bulk-memory support, pre-process the contract using
# wasm-opt to disable bulk memory.
WASM_OPT_BIN="${WASM_OPT_BIN:-$CONTRACTS_ROOT/tools/binaryen-version_116/bin/wasm-opt}"
WASM_OPT_DISABLE_BULK_MEMORY="${WASM_OPT_DISABLE_BULK_MEMORY:-1}"

# Prefer preventing bulk-memory ops at compile time.
WASM_RUSTFLAGS_DISABLE_BULK_MEMORY="${WASM_RUSTFLAGS_DISABLE_BULK_MEMORY:-1}"
BUILD_RUSTFLAGS="${BUILD_RUSTFLAGS:-}"

BIN="${BIN:-$PROJECT_ROOT/build/retrochaind}"
if [[ ! -x "$BIN" ]]; then
  BIN="retrochaind"
fi

say() { echo "==> $*"; }

txhash_from_out() {
  # read stdin
  python3 - <<'PY'
import re,sys
s=sys.stdin.read()
# common formats seen in cosmos sdk cli output
m=re.search(r"txhash:\s*([0-9A-Fa-f]+)", s)
if not m:
    m=re.search(r"'txhash':\s*'([0-9A-Fa-f]+)'", s)
if not m:
    m=re.search(r"\b([0-9A-Fa-f]{64})\b", s)
print(m.group(1) if m else "")
PY
}

wait_tx_json() {
  local hash="$1"
  for _ in $(seq 1 60); do
    if "$BIN" q tx "$hash" --node "$RPC" --output json >/tmp/tx.json 2>/dev/null; then
      cat /tmp/tx.json
      return 0
    fi
    sleep 1
  done
  return 1
}

event_attr() {
  # args: json, event_type, attr_key
  python3 - "$2" "$3" <<'PY'
import json,sys
etype=sys.argv[1]
key=sys.argv[2]
obj=json.load(sys.stdin)
logs=obj.get('logs') or []
for log in logs:
    for ev in log.get('events', []) or []:
        if ev.get('type') != etype:
            continue
        for a in ev.get('attributes', []) or []:
            if a.get('key') == key:
                print(a.get('value') or "")
                raise SystemExit(0)
print("")
PY
}

say "Building ra_cw721 WASM"
cd "$CONTRACTS_ROOT"
if [[ -z "$BUILD_RUSTFLAGS" && "$WASM_RUSTFLAGS_DISABLE_BULK_MEMORY" == "1" ]]; then
  BUILD_RUSTFLAGS="-C target-feature=-bulk-memory"
fi

if [[ -n "$BUILD_RUSTFLAGS" ]]; then
  say "Using RUSTFLAGS: $BUILD_RUSTFLAGS"
  RUSTFLAGS="$BUILD_RUSTFLAGS" cargo build --release --target wasm32-unknown-unknown -p ra_cw721
else
  cargo build --release --target wasm32-unknown-unknown -p ra_cw721
fi

if [[ ! -f "$WASM_PATH" ]]; then
  echo "WASM not found: $WASM_PATH" >&2
  exit 1
fi

if [[ "$WASM_OPT_DISABLE_BULK_MEMORY" == "1" && -x "$WASM_OPT_BIN" ]]; then
  say "Preprocessing WASM with wasm-opt (disable bulk-memory): $WASM_OPT_BIN"
  OPT_WASM="/tmp/ra_cw721.nobulk.$(date +%s).wasm"
  "$WASM_OPT_BIN" "$WASM_PATH" -o "$OPT_WASM" --strip-dwarf -Os --disable-bulk-memory
  WASM_PATH="$OPT_WASM"
  say "Using optimized WASM: $WASM_PATH"
fi

say "Checking wasm module is reachable"
"$BIN" q wasm params --node "$RPC" --output json >/dev/null 2>&1 || {
  echo "Wasm query failed. Either the node is down, RPC is wrong, or wasm isn't enabled on-chain yet." >&2
  echo "Tried: $BIN q wasm params --node $RPC" >&2
  exit 1
}

say "Storing code: $WASM_PATH"
STORE_OUT=$("$BIN" tx wasm store "$WASM_PATH" \
  --from "$KEY" \
  --keyring-backend "$KEYRING_BACKEND" \
  --node "$RPC" \
  --chain-id "$CHAIN_ID" \
  --home "$HOME_DIR" \
  --fees "$FEES" \
  --gas "$GAS" \
  --gas-adjustment "$GAS_ADJUSTMENT" \
  -y -b sync 2>&1 || true)

echo "$STORE_OUT"
TXHASH=$(printf '%s' "$STORE_OUT" | txhash_from_out)
if [[ -z "$TXHASH" ]]; then
  echo "Could not parse txhash from store output." >&2
  exit 1
fi

say "Waiting for tx $TXHASH"
TXJSON=$(wait_tx_json "$TXHASH") || { echo "Timed out waiting for tx: $TXHASH" >&2; exit 1; }
CODE_ID=$(printf '%s' "$TXJSON" | event_attr store_code code_id)
if [[ -z "$CODE_ID" ]]; then
  echo "Could not parse code_id from tx logs." >&2
  exit 1
fi
say "Stored code_id=$CODE_ID"

if [[ ! -f "$INSTANTIATE_MSG" ]]; then
  echo "Instantiate msg JSON not found: $INSTANTIATE_MSG" >&2
  exit 1
fi

say "Instantiating from: $INSTANTIATE_MSG"
INIT_OUT=$("$BIN" tx wasm instantiate "$CODE_ID" "$(cat "$INSTANTIATE_MSG")" \
  --from "$KEY" \
  --keyring-backend "$KEYRING_BACKEND" \
  --label "ra-cw721-$(date +%Y%m%d-%H%M%S)" \
  --no-admin \
  --node "$RPC" \
  --chain-id "$CHAIN_ID" \
  --home "$HOME_DIR" \
  --fees "$FEES" \
  --gas "$GAS" \
  --gas-adjustment "$GAS_ADJUSTMENT" \
  -y -b sync 2>&1 || true)

echo "$INIT_OUT"
TXHASH2=$(printf '%s' "$INIT_OUT" | txhash_from_out)
if [[ -z "$TXHASH2" ]]; then
  echo "Could not parse txhash from instantiate output." >&2
  exit 1
fi

say "Waiting for tx $TXHASH2"
TXJSON2=$(wait_tx_json "$TXHASH2") || { echo "Timed out waiting for tx: $TXHASH2" >&2; exit 1; }
CONTRACT=$(printf '%s' "$TXJSON2" | event_attr instantiate _contract_address)
if [[ -z "$CONTRACT" ]]; then
  # some chains emit "_contract_address" under "instantiate" or "wasm"
  CONTRACT=$(printf '%s' "$TXJSON2" | event_attr wasm _contract_address)
fi
if [[ -z "$CONTRACT" ]]; then
  echo "Could not parse contract address from tx logs." >&2
  exit 1
fi

say "Deployed CW721 contract: $CONTRACT"

say "Next: mint an NFT"
echo "$BIN tx wasm execute $CONTRACT '{"\"mint\"": {"\"token_id\"": "\"nft-0001\"", "\"owner\"": "\"<bech32>\"", "\"token_uri\"": "\"ipfs://...\""}}' --from $KEY --fees $FEES --gas $GAS --gas-adjustment $GAS_ADJUSTMENT --node $RPC --chain-id $CHAIN_ID --home $HOME_DIR -y"
