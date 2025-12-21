#!/usr/bin/env bash
set -euo pipefail

# Required inputs
UPGRADE_HEIGHT_JSON="${UPGRADE_HEIGHT_JSON:-/home/shaun/retrochain-rc1/contracts/ra/deploy/proposal_upgrade_rc1_nftfactory_v1.json}"
CHAIN_ID="${CHAIN_ID:-retrochain-mainnet}"
NODE="${NODE:-tcp://localhost:26657}"
FROM="${FROM:-foundation_validator}"
KEYRING_BACKEND="${KEYRING_BACKEND:-test}"

# Optional tweaks
DEPOSIT="${DEPOSIT:-50000000uretro}"
FEES="${FEES:-25000uretro}"
GAS_FLAGS="${GAS_FLAGS:---gas auto --gas-adjustment 1.3}"
RETROCHAIND_BIN="${RETROCHAIND_BIN:-retrochaind}"
# This chain's CLI supports broadcast modes: sync|async.
BROADCAST_MODE="${BROADCAST_MODE:-sync}"

if [[ ! -f "$UPGRADE_HEIGHT_JSON" ]]; then
  echo "proposal file not found: $UPGRADE_HEIGHT_JSON" >&2
  exit 1
fi

BEFORE_MAX_PID=$($RETROCHAIND_BIN q gov proposals --node "$NODE" -o json | jq -r '[.proposals[].id|tonumber] | max // 0')

# Basic guard: don't submit if an upgrade plan is already scheduled.
PLAN_JSON=$($RETROCHAIND_BIN q upgrade plan --node "$NODE" -o json 2>/dev/null || echo '{}')
if echo "$PLAN_JSON" | jq -e '.plan.name? and (.plan.name|length>0)' >/dev/null 2>&1; then
  echo "An upgrade plan is already scheduled; refusing to submit another software-upgrade proposal." >&2
  echo "$PLAN_JSON" | jq . >&2 || true
  exit 1
fi

# Ensure deposit/fees are consistent with uretro chain base denom
TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT
jq --arg deposit "$DEPOSIT" '.deposit=$deposit' "$UPGRADE_HEIGHT_JSON" > "$TMP"

echo "Submitting nftfactory upgrade proposal from $FROM ($CHAIN_ID @ $NODE)..."
PROP_OUTPUT=$($RETROCHAIND_BIN tx gov submit-proposal "$TMP" \
  --from "$FROM" \
  --keyring-backend "$KEYRING_BACKEND" \
  --chain-id "$CHAIN_ID" \
  --node "$NODE" \
  --broadcast-mode "$BROADCAST_MODE" \
  $GAS_FLAGS --fees "$FEES" -y -o json)

PID=$(echo "$PROP_OUTPUT" | jq -r '.logs[0].events[]? | select(.type=="submit_proposal").attributes[]? | select(.key=="proposal_id").value' 2>/dev/null || echo "")
if [[ -z "$PID" || "$PID" == "null" ]]; then
  # Some broadcast modes return empty logs; poll the max proposal ID until it increments.
  for _ in $(seq 1 30); do
    PID=$($RETROCHAIND_BIN q gov proposals --node "$NODE" -o json | jq -r '[.proposals[].id|tonumber] | max // empty')
    if [[ -n "$PID" ]] && (( PID > BEFORE_MAX_PID )); then
      break
    fi
    PID=""
    sleep 1
  done
fi
if [[ -z "$PID" || "$PID" == "null" ]]; then
  echo "Could not extract proposal ID. Raw output:" >&2
  echo "$PROP_OUTPUT" >&2
  exit 1
fi

echo "Proposal ID: $PID"
echo "Vote YES (optional):"
echo "  $RETROCHAIND_BIN tx gov vote $PID yes --from $FROM --keyring-backend $KEYRING_BACKEND --chain-id $CHAIN_ID --node $NODE $GAS_FLAGS --fees $FEES -y"
