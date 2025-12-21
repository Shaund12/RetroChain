# Hermes IBC Route: Osmosis (OSMO) ↔ RetroChain (RETRO)

This guide opens an **IBC transfer route** (ICS-20) between **Osmosis** (`osmosis-1`, OSMO) and **RetroChain** (`retrochain-mainnet`, RETRO).

Important:
- This creates an **IBC transfer channel**, not a swap.
- Once OSMO (or any other token) is on RetroChain as an `ibc/<hash>` voucher, you can:
  - transfer it back to Osmosis and swap on Osmosis, or
  - use Osmosis UI/wallets that support "swap after transfer" flows.

## Prereqs

- Hermes installed (`hermes version` works).
- Reachable **RPC + gRPC** endpoints for **each** chain.
  - RetroChain defaults (local): RPC `http://localhost:26657`, gRPC `http://localhost:9090`
  - Osmosis: use a reliable provider endpoint (RPC + gRPC).
- A funded relayer account on **both** chains:
  - Osmosis: some `uosmo` for fees
  - RetroChain: some `uretro` for fees

## 1) Create Hermes config

Start from the existing template and change the second chain to `osmosis-1`.

```bash
mkdir -p ~/.hermes
cp tools/ibc/hermes/config.example.toml ~/.hermes/config.toml
$EDITOR ~/.hermes/config.toml
```

Update the second `[[chains]]` section to:

- `id = "osmosis-1"`
- `rpc_addr = "https://..."`
- `grpc_addr = "https://..."`
- `key_name = "relayer-osmosis"`
- `gas_price.denom = "uosmo"`
- `event_source.url = "wss://.../websocket"`

Validate:

```bash
hermes config validate
```

## 2) Add relayer keys

Mnemonic file approach:

```bash
hermes keys add --chain retrochain-mainnet --mnemonic-file ./retro_relayer.mnemonic
hermes keys add --chain osmosis-1          --mnemonic-file ./osmo_relayer.mnemonic

hermes keys list --chain retrochain-mainnet
hermes keys list --chain osmosis-1
```

## 3) Create the IBC transfer channel (the “route”)

This creates:
- a **client** on each chain
- a **connection** between them
- a **channel** on port `transfer` (ICS-20)

```bash
hermes create channel \
  --a-chain retrochain-mainnet \
  --b-chain osmosis-1 \
  --a-port transfer \
  --b-port transfer \
  --new-client-connection \
  --yes
```

If your Hermes version doesn’t support `--new-client-connection`, use the older 3-step flow:

```bash
hermes create client     --a-chain retrochain-mainnet --b-chain osmosis-1
hermes create connection --a-chain retrochain-mainnet --b-chain osmosis-1
hermes create channel    --a-chain retrochain-mainnet --b-chain osmosis-1 --a-port transfer --b-port transfer
```

Record:
- `channel-XX` on RetroChain
- `channel-YY` on Osmosis

## 4) Start relaying

```bash
hermes start
```

## 5) Verify with a test transfer

### Osmosis → RetroChain (OSMO is received as an IBC voucher denom on RetroChain)

Using `osmosisd` (or any Osmosis wallet tooling):

```bash
# Replace channel-YY with the Osmosis-side transfer channel
# Replace <retro_address> with a RetroChain address (cosmos1...)

osmosisd tx ibc-transfer transfer transfer channel-YY <retro_address> 1000000uosmo \
  --from <osmo_key> --chain-id osmosis-1 --node <osmo_rpc>
```

### RetroChain → Osmosis (RETRO becomes an `ibc/<hash>` denom on Osmosis)

```bash
# Replace channel-XX with the RetroChain-side transfer channel
# Replace <osmo_address> with an Osmosis address (osmo1...)

retrochaind tx ibc-transfer transfer transfer channel-XX <osmo_address> 1000000uretro \
  --from <retro_key> --chain-id retrochain-mainnet --node tcp://localhost:26657
```

## 6) Swapping (Osmosis as the DEX)

Once funds are on Osmosis (native or as IBC vouchers), swaps happen on Osmosis.

Operationally you have two common flows:

1) **RetroChain → (IBC transfer) → Osmosis → swap on Osmosis UI**
2) **Osmosis → swap on Osmosis UI → (IBC transfer) → RetroChain**

Your explorer/front-end typically needs to:
- show balances on RetroChain including `ibc/<hash>` denoms
- resolve them via denom trace

```bash
# REST/LCD (replace <HASH> with the hash after "ibc/")
curl -s "http://localhost:1317/ibc/apps/transfer/v1/denom_traces/<HASH>" | jq
```

## Notes / gotchas

- Osmosis uses `osmo` bech32 prefix; RetroChain uses `cosmos`. Don’t mix up addresses.
- If txs fail with fee errors, raise `gas_price` in `~/.hermes/config.toml`.
- `trusting_period` must be **less than** the chain’s unbonding time.
