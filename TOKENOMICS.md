# RetroChain Tokenomics (RETRO)

This document defines RetroChain’s token economics **as configured in this repo**.

**Source of truth:**
- **Running network (retrochain-mainnet):** live node queries (REST/RPC) are authoritative for current parameters.
- **Dev template:** `config.yml` is a local/dev template and may not match the running network.

## TL;DR

- **Token symbol (display):** `RETRO`
- **Base denom (on-chain):** `uretro`
- **Decimals:** 6 (i.e. $1\ \text{RETRO} = 1{,}000{,}000\ \text{uretro}$)
- **Running network chain-id:** `retrochain-mainnet`
- **Dev template chain-id (`config.yml`):** `retrochain-arcade-1`
- **Genesis supply:**
  - **Running network:** $100{,}000{,}000\ \text{RETRO}$ at genesis
  - **Dev template (`config.yml`):** $21{,}000{,}000\ \text{RETRO}$ total ($21{,}000{,}000{,}000{,}000\ \text{uretro}$)
- **Supply cap / max supply (running network):** **No fixed hard cap** (inflationary; supply can grow indefinitely while minting is enabled)
- **Current supply (running network):** 100,059,692.892038 RETRO at height 28916 (from `bank/supply/by_denom?denom=uretro`)
- **Inflation (running network `mint` params):**
  - min: `0.070000000000000000`
  - max: `0.200000000000000000`
  - rate_change: `0.130000000000000000`
  - goal_bonded: `0.670000000000000000`
  - blocks_per_year: `6311520`
- **Live inflation (running network):** `0.130506802730613793` (from `/cosmos/mint/v1beta1/inflation`)
- **Annual provisions (running network):** `13058476271900.662837219873488887` uretro/year (from `/cosmos/mint/v1beta1/annual_provisions`)
- **Staking bond denom:** `uretro`
- **Unbonding time:** `1814400s` (21 days)
- **Governance min deposit (running network):** `10000000uretro` (10 RETRO)
- **Crisis constant fee:** `1000000uretro` (1 RETRO)

## Denominations

RetroChain uses a 6-decimal native token:

- Base denom: `uretro`
- Display denom: `RETRO`

Conversion:

$$
\text{RETRO} = \frac{\text{uretro}}{10^6}
$$

Denom metadata (from `config.yml`):
- `base`: `uretro`
- `display`: `RETRO`
- units: `uretro` (0), `mretro` (3), `RETRO` (6)

## Genesis supply & allocations

### Dev template allocations (from `config.yml`)

`config.yml` defines three funded genesis accounts:

- `alice`: `10000000000000uretro` (10,000,000 RETRO)
- `bob`: `5000000000000uretro` (5,000,000 RETRO)
- `dev`: `6000000000000uretro` (6,000,000 RETRO)

Total genesis supply implied by these allocations:

- $10{,}000{,}000 + 5{,}000{,}000 + 6{,}000{,}000 = 21{,}000{,}000\ \text{RETRO}$

### Running network genesis supply (mainnet/testnet)

The **running RetroChain network** has **100,000,000 RETRO at genesis**.

Important nuance: on-chain “genesis allocations” are split across **liquid account balances** and **staked (bonded) tokens**.

#### On-chain balances at height 1 (liquid accounts)

Balances below are queried with `x-cosmos-block-height: 1` against `/cosmos/bank/v1beta1/balances/<addr>`:

- `foundation_validator` (liquid): `40000000000000uretro` (40,000,000 RETRO)
- `ecosystem_rewards`: `20000000000000uretro` (20,000,000 RETRO)
- `liquidity_fund`: `10000000000000uretro` (10,000,000 RETRO)
- `community_fund`: `7000000000000uretro` (7,000,000 RETRO)
- `dev_fund`: `6000000000000uretro` (6,000,000 RETRO)
- `shaun_profit`: `5000000000000uretro` (5,000,000 RETRO)
- `kitty_charity`: `2000000000000uretro` (2,000,000 RETRO)

Subtotal (liquid, these 7 accounts): **90,000,000 RETRO**

#### On-chain staking at height 1 (bonded)

At height 1, `foundation_validator` has a delegation of:

- `10000000000000uretro` (10,000,000 RETRO) to `cosmosvaloper1fscvf7rphx477z6vd4sxsusm2u8a70ketcvjzh`

This explains the remaining 10,000,000 RETRO being held by the `bonded_tokens_pool` module account at height 1.

#### Total supply at height 1

At height 1, the chain reports total supply:

- `100000002059725uretro` (100,000,002.059725 RETRO)

That is **slightly above** 100,000,000 RETRO due to first-block minting/fees landing in module accounts (e.g. `fee_collector`).

This repo currently does not include the canonical `genesis.json` used to start `retrochain-mainnet`, so the most auditable breakdown in-repo is via on-chain height-1 queries (as above).

If you drop in the real `genesis.json` (or a valid `retrochaind export` JSON) we can extend this section with a complete genesis-state accounting (all module accounts, vesting, pools, etc.).

#### Early post-genesis redistribution (operator-controlled)

Several large transfers occurred early in chain history that “reshuffled” these treasury balances. The key ones (decoded from on-chain txs):

- height 110: `foundation_validator` → `community_fund` **20,000,000 RETRO**
- height 141: `foundation_validator` → `liquidity_fund` **5,000,000 RETRO**
- height 142: `foundation_validator` → `dev_fund` **4,000,000 RETRO** (bringing `dev_fund` to ~10,000,000 RETRO)
- height 146: `shaun_profit` → `foundation_validator` **2,000,000 RETRO**

### Genesis validator bond (from `config.yml`)

`config.yml` also defines a genesis validator:

- validator: `alice`
- bonded: `1000000000000uretro` (1,000,000 RETRO)

## Staking & security parameters

Running network (from `/cosmos/staking/v1beta1/params`):

- `bond_denom`: `uretro`
- `unbonding_time`: `1814400s` (21 days)
- `max_validators`: `100`
- `max_entries`: `7`
- `historical_entries`: `10000`

## Inflation & issuance (Mint module)

Running network (from `/cosmos/mint/v1beta1/params`):

- `mint_denom`: `uretro`
- `inflation_rate_change`: `0.130000000000000000`
- `inflation_max`: `0.200000000000000000`
- `inflation_min`: `0.070000000000000000`
- `goal_bonded`: `0.670000000000000000`
- `blocks_per_year`: `6311520`

Notes:
- RetroChain uses the Cosmos SDK mint module’s bonded-ratio targeting model. Exact per-block issuance depends on network state (bonded ratio) and these parameters.
- **No hard cap:** because `inflation_min` is non-zero and minting is enabled, the maximum possible supply is not fixed (it increases over time unless minting is disabled or inflation is set to 0 via governance).

## Treasury / early tester distributions

The `dev_fund` wallet has been used to distribute tokens to early testers.

On-chain, three transfers of **500,000 RETRO** each were observed from `dev_fund` (each plus fees) at:

- height 19255 → `cosmos1xct40mu2p6sl54w5cw9yad07tcff5eqvkp65r6`
- height 27508 → `cosmos1ful20t02g95zjq5j8kghunhcu82l8nj36jaseq`
- height 27893 → `cosmos1esun5s55tn0hhd287fjwxkc28sp0ueqtrhtx4k`

## Distribution (staking rewards)

Running network (from `/cosmos/distribution/v1beta1/params`):

- `community_tax`: `0.020000000000000000` (2%)
- `withdraw_addr_enabled`: `true`

## Fees, minimum gas prices, and crisis fee

### Minimum gas prices

`config.yml` does not set `app.toml` values, but the Node Manager `Setup` tab defaults to `0uretro`.

Operators should set a non-zero `minimum-gas-prices` for public networks to reduce mempool spam.

### Crisis fee

From `config.yml` → `genesis.app_state.crisis.constant_fee`:

- `1000000uretro` (1 RETRO)

## Governance economics

Running network (from `/cosmos/gov/v1/params/*`):

- `min_deposit`: `10000000uretro` (10 RETRO)
- `max_deposit_period`: `172800s` (2 days)
- `voting_period`: `172800s` (2 days)
- `quorum`: `0.334000000000000000`
- `threshold`: `0.500000000000000000`
- `veto_threshold`: `0.334000000000000000`

## Arcade economy hooks

RetroChain’s `x/arcade` module parameters in `config.yml` define in-game economic constants such as:

- `base_credits_cost`: `1000000` (interpreted by the module; see Arcade docs)
- `tokens_per_thousand_points`: `1`
- `tournament_registration_fee`: `10000000`

For the full player-facing explanation of how arcade credits/rewards work, see `ARCADE_GUIDE.md` and `ARCADE_GAMES.md`.

## Burn mechanics & RA (RetroArcade) contracts

### On-chain burn module (`x/burn`)

This repo includes a custom module `x/burn` with parameters:

- `fee_burn_rate`
- `provision_burn_rate`

Code defaults (from `x/burn/types/params.go`) are conservative:

- `fee_burn_rate = 0.05` (5%)
- `provision_burn_rate = 0.00` (0%)

If the network intends a different split, it must be set via genesis or governance/params.

### RA Converter design (CosmWasm)

`contracts/ra/README.md` describes an intended flow for an RA CW20 token:

- `ra_converter` accepts `uretro`, forwards **100%** to the chain fee collector.
- The intended downstream split (per that doc) is “~80% burn / ~20% to stakers”.

Important: the **current enforced split depends on the live `x/burn` parameters** (and any additional fee collector handling). The “80/20” figure is a stated intent in `contracts/ra/README.md`, not a value currently defined in `config.yml`.

## Faucet (dev/test networks)

From `config.yml`:

- faucet account: `alice`
- faucet coins: `10000000uretro` (10 RETRO)
- faucet max: `1000000000uretro` (1,000 RETRO)
- port: `4500`

## How to verify live tokenomics on a running node

Use the CLI against a running node:

```bash
retrochaind query bank total --denom uretro
retrochaind query staking params
retrochaind query mint params
retrochaind query distribution params
retrochaind query gov params
```

### Genesis supply vs current supply

- `retrochaind query bank total --denom uretro` reports **current** total supply.
- If inflation is enabled (mint module), **current supply increases over time**, so it will exceed genesis supply.

To verify genesis supply precisely you need one of:
- The original `genesis.json` used at height 1 (sum all `bank.balances` for `uretro` plus any module-account balances), or
- A historical/archival query/export pinned to height 1.

If your node provides historical state and supports `--height`, you can try:

```bash
retrochaind query bank total --denom uretro --height 1
```

(Many nodes prune and won’t serve height 1; in that case use the genesis file or an export snapshot.)

If `x/burn` exposes queries in your build, use its CLI query (see `x/burn/client/cli/query.go`).

## Open items / TBD

If you want this document to be a mainnet contract, we should explicitly define (and/or add to genesis) the following:

- Treasury/community pool funding amounts and addresses
- Any vesting schedules / cliff / unlock policies
- Whether burn rates differ from the `x/burn` defaults (5%/0%)
- Treasury/community pool funding amounts and addresses
- Any vesting schedules / cliff / unlock policies
- Whether burn rates differ from the `x/burn` defaults (5%/0%)
