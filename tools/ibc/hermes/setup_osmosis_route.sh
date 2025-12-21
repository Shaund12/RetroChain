#!/usr/bin/env bash
set -euo pipefail

# Creates the RetroChain <-> Osmosis IBC transfer channel (ICS-20) using Hermes.
#
# Prereqs:
# - Hermes installed
# - ~/.hermes/config.toml configured for retrochain-mainnet + osmosis-1
# - Keys imported:
#     hermes keys add --chain retrochain-mainnet --mnemonic-file ./retro_relayer.mnemonic
#     hermes keys add --chain osmosis-1          --mnemonic-file ./osmo_relayer.mnemonic

A_CHAIN="retrochain-mainnet"
B_CHAIN="osmosis-1"

echo "Validating Hermes config..."
hermes config validate

echo "Listing keys (must exist on both chains)..."
hermes keys list --chain "$A_CHAIN" || true
hermes keys list --chain "$B_CHAIN" || true

echo "Creating IBC transfer channel (this also creates clients + connection)..."
set +e
hermes create channel \
  --a-chain "$A_CHAIN" \
  --b-chain "$B_CHAIN" \
  --a-port transfer \
  --b-port transfer \
  --new-client-connection \
  --yes
rc=$?
set -e

if [[ $rc -ne 0 ]]; then
  echo "hermes create channel failed (maybe your Hermes version doesn't support --new-client-connection)."
  echo "Falling back to the 3-step flow (client -> connection -> channel)..."
  hermes create client     --a-chain "$A_CHAIN" --b-chain "$B_CHAIN"
  hermes create connection --a-chain "$A_CHAIN" --b-chain "$B_CHAIN"
  hermes create channel    --a-chain "$A_CHAIN" --b-chain "$B_CHAIN" --a-port transfer --b-port transfer
fi

echo
echo "Done. Copy the channel IDs from the output above (RetroChain channel-XX, Osmosis channel-YY)."
echo "Next: run 'hermes start' in a separate terminal to relay packets."
