#!/usr/bin/env bash
set -euo pipefail

# Required inputs
CHAIN_ID="${CHAIN_ID:-}"
FROM="${FROM:-}"
UPGRADE_HEIGHT="${UPGRADE_HEIGHT:-}"
FEE_DENOM="${FEE_DENOM:-stake}"

# Optional tweaks
DEPOSIT="${DEPOSIT:-1000000$FEE_DENOM}"
FEES="${FEES:-2500$FEE_DENOM}"
GAS_FLAGS="${GAS_FLAGS:---gas auto --gas-adjustment 1.3}"
TITLE="${TITLE:-Enable burn module (rc1-burn-v1)}"
DESC="${DESC:-Adds burn store key and enables fee/provision burning (defaults fee_burn_rate=0.05, provision_burn_rate=0.00).}"

if [[ -z "$CHAIN_ID" || -z "$FROM" || -z "$UPGRADE_HEIGHT" ]]; then
  echo "Set CHAIN_ID, FROM, and UPGRADE_HEIGHT env vars before running."
  exit 1
fi

echo "Submitting proposal rc1-burn-v1 at height $UPGRADE_HEIGHT..."
PROP_OUTPUT=$(retrochaind tx gov submit-proposal software-upgrade rc1-burn-v1 \
  --upgrade-height "$UPGRADE_HEIGHT" \
  --title "$TITLE" \
  --description "$DESC" \
  --deposit "$DEPOSIT" \
  --from "$FROM" \
  --chain-id "$CHAIN_ID" \
  $GAS_FLAGS --fees "$FEES" -y -o json)

# Extract proposal ID (assumes JSON output)
PID=$(echo "$PROP_OUTPUT" | jq -r '.logs[0].events[] | select(.type=="submit_proposal").attributes[] | select(.key=="proposal_id").value')
if [[ -z "$PID" || "$PID" == "null" ]]; then
  echo "Could not extract proposal ID. Raw output:"
  echo "$PROP_OUTPUT"
  exit 1
fi
echo "Proposal ID: $PID"

echo "Voting YES with $FROM..."
retrochaind tx gov vote "$PID" yes \
  --from "$FROM" \
  --chain-id "$CHAIN_ID" \
  $GAS_FLAGS --fees "$FEES" -y

echo "Done. Monitor proposal status with:"
echo "  retrochaind q gov proposal $PID"
