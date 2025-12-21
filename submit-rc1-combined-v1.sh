#!/usr/bin/env bash
set -euo pipefail

# Required inputs
PROPOSAL_JSON="${PROPOSAL_JSON:-/home/shaun/retrochain-rc1/contracts/ra/deploy/proposal_upgrade_rc1_combined_v1.json}"
CHAIN_ID="${CHAIN_ID:-retrochain-mainnet}"
NODE="${NODE:-tcp://localhost:26657}"
FROM="${FROM:-foundation_validator}"
KEYRING_BACKEND="${KEYRING_BACKEND:-test}"

# Optional tweaks
DEPOSIT="${DEPOSIT:-50000000uretro}"
FEES="${FEES:-25000uretro}"
GAS_FLAGS="${GAS_FLAGS:---gas auto --gas-adjustment 1.3}"

if [[ ! -f "$PROPOSAL_JSON" ]]; then
  echo "proposal file not found: $PROPOSAL_JSON" >&2
  exit 1
fi

# Guard: only one upgrade plan can be scheduled at a time.
PLAN_JSON=$(retrochaind q upgrade plan --node "$NODE" -o json 2>/dev/null || echo '{}')
if echo "$PLAN_JSON" | jq -e '.plan.name? and (.plan.name|length>0)' >/dev/null 2>&1; then
  echo "An upgrade plan is already scheduled; refusing to submit another software-upgrade proposal." >&2
  echo "$PLAN_JSON" | jq . >&2 || true
  exit 1
fi

TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT
jq --arg deposit "$DEPOSIT" '.deposit=$deposit' "$PROPOSAL_JSON" > "$TMP"

echo "Submitting combined upgrade proposal from $FROM ($CHAIN_ID @ $NODE)..."
PROP_OUTPUT=$(retrochaind tx gov submit-proposal "$TMP" \
  --from "$FROM" \
  --keyring-backend "$KEYRING_BACKEND" \
  --chain-id "$CHAIN_ID" \
  --node "$NODE" \
  $GAS_FLAGS --fees "$FEES" -y -o json)

PID=$(echo "$PROP_OUTPUT" | jq -r '.logs[0].events[] | select(.type=="submit_proposal").attributes[] | select(.key=="proposal_id").value')
if [[ -z "$PID" || "$PID" == "null" ]]; then
  echo "Could not extract proposal ID. Raw output:" >&2
  echo "$PROP_OUTPUT" >&2
  exit 1
fi

echo "Proposal ID: $PID"
echo "Vote YES (optional):"
echo "  retrochaind tx gov vote $PID yes --from $FROM --keyring-backend $KEYRING_BACKEND --chain-id $CHAIN_ID --node $NODE $GAS_FLAGS --fees $FEES -y"
