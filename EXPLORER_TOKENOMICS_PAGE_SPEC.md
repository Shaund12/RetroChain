# RetroChain Explorer — Tokenomics Page Spec

This document is a **build spec** for adding a **Tokenomics** page to a RetroChain explorer UI.

Goals:
- Show **authoritative, live** tokenomics numbers from the running chain.
- Keep the page **read-only**.
- Keep it **simple**: one page, a handful of sections, no extra filters/modals.

Non-goals:
- No charts required.
- No historical time-series.
- No transaction decoding.

---

## Chain constants (must match RetroChain)

- **chain-id (running network):** `retrochain-mainnet`
- **base denom (on-chain):** `uretro`
- **display denom:** `RETRO`
- **decimals:** 6
- Conversion: $1\ \text{RETRO} = 1{,}000{,}000\ \text{uretro}$

---

## Data sources (authoritative)

Use the explorer’s existing Cosmos REST client (LCD). These endpoints are standard Cosmos SDK endpoints.

Base REST examples below assume:
- `REST = http://127.0.0.1:1317`

### Snapshot height (display on page)

Fetch latest block height/time once and display it as “Data as of height …”.

- `GET /cosmos/base/tendermint/v1beta1/blocks/latest`
  - `block.header.height`
  - `block.header.time`

---

## Page layout (required sections)

Implement the following sections in this order.

### 1) Token

Display:
- Symbol: `RETRO`
- Base denom: `uretro`
- Decimals: `6`

Formatting rules:
- When showing on-chain integer amounts, convert uretro → RETRO using `amount / 1_000_000`.
- Display up to 6 decimals; trim trailing zeros for readability.

---

### 2) Supply

**A. Current total supply (live)**

- `GET /cosmos/bank/v1beta1/supply/by_denom?denom=uretro`
  - Read: `amount.amount` (string integer uretro)

Show:
- “Current supply”: `<currentSupplyRETRO> RETRO`

**B. Genesis supply (constant for this network)**

Show as static text:
- “Genesis supply (retrochain-mainnet): 100,000,000 RETRO”

**C. Supply cap / max supply**

Show as static text:
- “Max supply: **No fixed hard cap** (inflationary while minting is enabled).”

Optional derived field:
- “Net minted since genesis”: `currentSupply - 100,000,000` (RETRO)

---

### 3) Mint / Inflation (live)

**A. Mint params**

- `GET /cosmos/mint/v1beta1/params`
  - `params.mint_denom`
  - `params.inflation_rate_change`
  - `params.inflation_max`
  - `params.inflation_min`
  - `params.goal_bonded`
  - `params.blocks_per_year`

Display each field exactly as returned (strings).

**B. Live inflation**

- `GET /cosmos/mint/v1beta1/inflation`
  - `inflation` (string decimal)

**C. Annual provisions**

- `GET /cosmos/mint/v1beta1/annual_provisions`
  - `annual_provisions` (string decimal, in uretro/year)

Derived fields (recommended):
- Annual provisions (RETRO/year): `annual_provisions / 1e6`
- Daily estimate (RETRO/day): `(annual_provisions / 1e6) / 365`
- Per-block estimate (RETRO/block): `(annual_provisions / 1e6) / blocks_per_year`

Note: these are estimates based on current parameters and current chain state.

---

### 4) Staking params (live)

- `GET /cosmos/staking/v1beta1/params`
  - `params.bond_denom`
  - `params.unbonding_time`
  - `params.max_validators`
  - `params.max_entries`
  - `params.historical_entries`

Display:
- Bond denom (expect `uretro`)
- Unbonding time (expect `1814400s` on current network)

---

### 5) Distribution params (live)

- `GET /cosmos/distribution/v1beta1/params`
  - `params.community_tax`
  - `params.withdraw_addr_enabled`

---

### 6) Governance economics (live)

Use the v1 gov params endpoints:

- Deposit params: `GET /cosmos/gov/v1/params/deposit`
  - Show `deposit_params.min_deposit[]` (find denom `uretro`)
  - Show `deposit_params.max_deposit_period`

- Voting params: `GET /cosmos/gov/v1/params/voting`
  - Show `voting_params.voting_period`

- Tally params: `GET /cosmos/gov/v1/params/tallying`
  - Show `tally_params.quorum`
  - Show `tally_params.threshold`
  - Show `tally_params.veto_threshold`

---

### 7) Genesis allocations (audited constants)

These values are intentionally **static** (they document the initial design and height-1 accounting).

#### A. Height-1 liquid balances (sum = 90,000,000 RETRO)

Display as a simple table (Name, Address, Amount):

- `foundation_validator` — `cosmos1fscvf7rphx477z6vd4sxsusm2u8a70kewvc8wy` — 40,000,000 RETRO (liquid)
- `ecosystem_rewards` — `cosmos1exqr633rjzls2h4txrpu0cxhnxx0dquylf074x` — 20,000,000 RETRO
- `liquidity_fund` — `cosmos1w506apt4kyq72xgaakwxrvak8w5d94upn3gdf3` — 10,000,000 RETRO
- `community_fund` — `cosmos1tksjh4tkdjfnwkkwty0wyuy4pv93q5q4lepgrn` — 7,000,000 RETRO
- `dev_fund` — `cosmos1epy8qnuu00w76xvvlt2mc7q8qslhw206vzu5vs` — 6,000,000 RETRO
- `shaun_profit` — `cosmos1us0jjdd5dj0v499g959jatpnh6xuamwhwdrrgq` — 5,000,000 RETRO
- `kitty_charity` — `cosmos1ydn44ufvhddqhxu88m709k46hdm0dfjwm8v0tt` — 2,000,000 RETRO

#### B. Height-1 bonded stake (sum = 10,000,000 RETRO)

Static explanation text:
- At height 1, `foundation_validator` has **10,000,000 RETRO** delegated (bonded), which is why 10M appears in the chain’s bonded pool instead of as a liquid balance.

Validator operator (for linking):
- `cosmosvaloper1fscvf7rphx477z6vd4sxsusm2u8a70ketcvjzh`

---

### 8) Early post-genesis treasury redistributions (audited constants)

Display as a short bullet list (Height, From, To, Amount):

- height 110: `foundation_validator` → `community_fund` — 20,000,000 RETRO
- height 141: `foundation_validator` → `liquidity_fund` — 5,000,000 RETRO
- height 142: `foundation_validator` → `dev_fund` — 4,000,000 RETRO
- height 146: `shaun_profit` → `foundation_validator` — 2,000,000 RETRO

---

### 9) Treasury / early tester distributions (audited constants)

Static explanation text:
- The `dev_fund` wallet has been used to distribute tokens to early testers.

Show the known 500,000 RETRO payouts (Height, To):
- height 19255 → `cosmos1xct40mu2p6sl54w5cw9yad07tcff5eqvkp65r6`
- height 27508 → `cosmos1ful20t02g95zjq5j8kghunhcu82l8nj36jaseq`
- height 27893 → `cosmos1esun5s55tn0hhd287fjwxkc28sp0ueqtrhtx4k`

---

### 10) Arcade economy parameters (live)

These are chain params that affect gameplay economics.

- `GET /retrochain/arcade/v1/params`

Display the returned params object as a list of key/value pairs (no special formatting required).

---

## Error handling & fallbacks

- If any live endpoint fails, show `—` for that field and keep the rest of the page rendering.
- Always show the “Data as of height …” row only if the latest-block endpoint succeeds.

---

## Implementation notes (for Copilot)

- Fetch live endpoints in parallel.
- Treat numeric values from REST as strings; use big-number parsing where needed.
- Do not invent new economics values; if it’s not in REST responses or in the static audited lists above, omit it.

---

## Reference

- Canonical tokenomics narrative: `TOKENOMICS.md`
