#!/usr/bin/env bash
set -euo pipefail

# Mints a test NFT on a deployed ra_cw721 contract with an embedded SVG image.
#
# Usage:
#   CONTRACT=<addr> KEYRING_BACKEND=test KEY=foundation_validator \
#     ./contracts/ra/deploy/mint_test_ra_cw721.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

BIN="${BIN:-$PROJECT_ROOT/build/retrochaind}"
if [[ ! -x "$BIN" ]]; then
  BIN="retrochaind"
fi
HOME_DIR="${HOME_DIR:-$HOME/.retrochain}"
NODE="${NODE:-tcp://localhost:26657}"
CHAIN_ID="${CHAIN_ID:-retrochain-mainnet}"
KEY="${KEY:-foundation_validator}"
KEYRING_BACKEND="${KEYRING_BACKEND:-test}"
GAS_PRICES="${GAS_PRICES:-0.003uretro}"

CONTRACT="${CONTRACT:-}"
TOKEN_ID="${TOKEN_ID:-nft-0001}"

if [[ -z "$CONTRACT" ]]; then
  echo "CONTRACT is required" >&2
  exit 1
fi

OWNER_ADDR="$($BIN keys show "$KEY" --home "$HOME_DIR" --keyring-backend "$KEYRING_BACKEND" --address)"

SVG_PATH="${SVG_PATH:-$SCRIPT_DIR/retroarcade_nft_image.svg}"
META_TEMPLATE="${META_TEMPLATE:-$SCRIPT_DIR/retroarcade_nft_metadata.template.json}"

if [[ ! -f "$SVG_PATH" ]]; then
  echo "Missing SVG: $SVG_PATH" >&2
  exit 1
fi
if [[ ! -f "$META_TEMPLATE" ]]; then
  echo "Missing metadata template: $META_TEMPLATE" >&2
  exit 1
fi

SVG_B64="$(base64 -w0 < "$SVG_PATH")"
IMAGE_URI="data:image/svg+xml;base64,${SVG_B64}"

# Fill metadata JSON, then base64 it and make a data: URI.
META_JSON="$(python3 - <<PY
import json
from pathlib import Path
p=Path("$META_TEMPLATE")
obj=json.loads(p.read_text())
obj["image"]="$IMAGE_URI"
print(json.dumps(obj,separators=(",",":")))
PY
)"
META_B64="$(printf '%s' "$META_JSON" | base64 -w0)"
TOKEN_URI="data:application/json;base64,${META_B64}"

EXEC_MSG="$(python3 - <<PY
import json
print(json.dumps({"mint": {"token_id": "$TOKEN_ID", "owner": "$OWNER_ADDR", "token_uri": "$TOKEN_URI"}}, separators=(",",":")))
PY
)"

set -x
$BIN tx wasm execute "$CONTRACT" "$EXEC_MSG" \
  --from "$KEY" \
  --home "$HOME_DIR" \
  --keyring-backend "$KEYRING_BACKEND" \
  --chain-id "$CHAIN_ID" \
  --node "$NODE" \
  --broadcast-mode sync \
  --gas 400000 \
  --gas-prices "$GAS_PRICES" \
  -y \
  --output json

# Query token info back
$BIN query wasm contract-state smart "$CONTRACT" "$(python3 - <<PY
import json
print(json.dumps({"nft_info": {"token_id": "$TOKEN_ID"}}, separators=(",",":")))
PY
)" --node "$NODE" --output json
