#!/usr/bin/env bash
set -euo pipefail

BIN="${BIN:-/home/shaun/retrochain-rc1/build/retrochaind}"
HOME_DIR="${HOME_DIR:-/home/shaun/.retrochain}"
NODE="${NODE:-tcp://localhost:26657}"
CHAIN_ID="${CHAIN_ID:-retrochain-mainnet}"
KEY_NAME="${KEY_NAME:-foundation_validator}"
KEYRING_BACKEND="${KEYRING_BACKEND:-test}"
GAS_PRICES="${GAS_PRICES:-0.003uretro}"

SUBDENOM="${SUBDENOM:-retroarcade}"
# Matches contracts/ra/deploy/instantiate_ra_cw20_100b.json (100B with 6 decimals)
AMOUNT_BASE_UNITS="${AMOUNT_BASE_UNITS:-100000000000000000}"

ADDR="$($BIN keys show "$KEY_NAME" --home "$HOME_DIR" --keyring-backend "$KEYRING_BACKEND" --address)"
DENOM="factory/${ADDR}/${SUBDENOM}"

set -x

# Create denom (idempotent-ish): if already exists, the tx will fail; in that case we keep going.
$BIN tx tokenfactory create-denom "$SUBDENOM" \
  --from "$KEY_NAME" \
  --home "$HOME_DIR" \
  --keyring-backend "$KEYRING_BACKEND" \
  --chain-id "$CHAIN_ID" \
  --node "$NODE" \
  --broadcast-mode sync \
  --gas 150000 \
  --gas-prices "$GAS_PRICES" \
  -y \
  --output json || true

# Confirm admin
$BIN query tokenfactory denom-authority-metadata \
  --denom "$DENOM" \
  --node "$NODE" \
  --output json

# Mint initial supply to the admin address
$BIN tx tokenfactory mint "${AMOUNT_BASE_UNITS}${DENOM}" \
  --mint-to-address "$ADDR" \
  --from "$KEY_NAME" \
  --home "$HOME_DIR" \
  --keyring-backend "$KEYRING_BACKEND" \
  --chain-id "$CHAIN_ID" \
  --node "$NODE" \
  --broadcast-mode sync \
  --gas 250000 \
  --gas-prices "$GAS_PRICES" \
  -y \
  --output json

# Verify balance
$BIN query bank balance "$ADDR" "$DENOM" --node "$NODE" --output json
