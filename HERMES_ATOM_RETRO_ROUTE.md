# Hermes IBC Route: Cosmos Hub (ATOM) ↔ RetroChain (RETRO)

This guide opens an **IBC transfer route** (ICS-20) between **Cosmos Hub** (`cosmoshub-4`, ATOM) and **RetroChain** (`retrochain-mainnet`, RETRO).

Important: this is **not a swap**. ATOM transferred to RetroChain remains **ATOM**, but it will be represented on RetroChain as an **IBC voucher denom** (e.g. `ibc/<hash>`). UIs typically resolve that back to `uatom` / `ATOM` via the denom-trace endpoint.

## Prereqs

- Hermes installed (`hermes version` works).
- A reachable **RPC + gRPC** endpoint for **each** chain.
  - RetroChain defaults (local): RPC `http://localhost:26657`, gRPC `http://localhost:9090`
  - Cosmos Hub: use a reliable provider endpoint (RPC + gRPC).
- A funded relayer account on **both** chains:
  - Hub: some `uatom` for fees
  - RetroChain: some `uretro` for fees

## 1) Create Hermes config

Copy the template and edit the Hub endpoints + gas prices:

```bash
mkdir -p ~/.hermes
cp tools/hermes/config.toml.example ~/.hermes/config.toml
$EDITOR ~/.hermes/config.toml
```

Validate:

```bash
hermes config validate
```

## 2) Add relayer keys

Add/import a key for each chain (use your preferred method).

Mnemonic file approach:

```bash
# Create files containing a mnemonic (12/24 words) on a single line
# Then import them:
hermes keys add --chain retrochain-mainnet --mnemonic-file ./retro_relayer.mnemonic
hermes keys add --chain cosmoshub-4        --mnemonic-file ./hub_relayer.mnemonic

hermes keys list --chain retrochain-mainnet
hermes keys list --chain cosmoshub-4
```

## 3) Create the IBC transfer channel (the “route”)

This creates:
- a **client** on each chain
- a **connection** between them
- a **channel** on port `transfer` (ICS-20)

```bash
hermes create channel \
  --a-chain retrochain-mainnet \
  --b-chain cosmoshub-4 \
  --a-port transfer \
  --b-port transfer \
  --new-client-connection \
  --yes
```

If your Hermes version doesn’t support `--new-client-connection`, use the older 3-step flow:

```bash
hermes create client     --a-chain retrochain-mainnet --b-chain cosmoshub-4
hermes create connection --a-chain retrochain-mainnet --b-chain cosmoshub-4
hermes create channel    --a-chain retrochain-mainnet --b-chain cosmoshub-4 --a-port transfer --b-port transfer
```

After creation, record:
- `channel-XX` on RetroChain
- `channel-YY` on Cosmos Hub

(You’ll need them for explorers and for `ibc-transfer` commands.)

## 4) Start relaying

```bash
hermes start
```

## 5) Verify by sending a test transfer

### Hub → RetroChain (ATOM is received as an IBC voucher denom on RetroChain)

Using `gaiad` (or any Cosmos Hub wallet tooling):

```bash
# Replace channel-YY with the Hub-side transfer channel
# Replace <retro_address> with a RetroChain address (cosmos1...)

gaiad tx ibc-transfer transfer transfer channel-YY <retro_address> 100000uatom \
  --from <hub_key> --chain-id cosmoshub-4 --node <hub_rpc>
```

### RetroChain → Hub (RETRO becomes an `ibc/<hash>` denom on Hub)

Using `retrochaind`:

```bash
# Replace channel-XX with the RetroChain-side transfer channel
# Replace <hub_address> with a Hub address (cosmos1...)

retrochaind tx ibc-transfer transfer transfer channel-XX <hub_address> 1000000uretro \
  --from <retro_key> --chain-id retrochain-mainnet --node tcp://localhost:26657
```

## 6) Show “ATOM” (not just `ibc/<hash>`) on RetroChain

After a Hub → RetroChain transfer, you can discover the local IBC denom and resolve it:

1) Find the balance denom on RetroChain:

```bash
retrochaind q bank balances <retro_address> --node tcp://localhost:26657
```

You’ll see a denom like `ibc/<HASH>`.

2) Resolve the denom trace (this proves it’s `uatom` from Cosmos Hub):

```bash
# REST/LCD
curl -s "http://localhost:1317/ibc/apps/transfer/v1/denom_traces/<HASH>" | jq
```

The response includes:
- `denom_trace.base_denom` (expect `uatom`)
- `denom_trace.path` (the transfer path)

Explorer/display logic should show symbol **ATOM** when `base_denom` is `uatom`.

## Notes / gotchas

- Both chains use the `cosmos` bech32 prefix; that’s OK, but don’t confuse which key is funded on which chain.
- If txs fail with fee errors, raise the `gas_price` in `~/.hermes/config.toml`.
- `trusting_period` must be **less than** the chain’s unbonding time.
