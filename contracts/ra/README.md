# RA Contracts

This folder contains two CosmWasm contracts:

- `ra_cw20`: a thin wrapper around `cw20-base` for the RetroArcade (RA) CW20 token.
- `ra_converter`: converts funded `uretro` deposits into RA 1:1 and forwards the native deposit to the chain fee-collector address.

## Tokenomics wiring

The converter forwards **100%** of deposited `uretro` to `fee_collector_addr`.

The intended split is achieved on the chain side:

- `x/burn` burns ~80% from fee collector
- the remaining ~20% is distributed to stakers (distribution)

So: deposit `uretro` → fee collector → (burn + stakers), while minting RA 1:1 to the user.

## Build

Prereqs:

- Rust + Cargo
- wasm target: `rustup target add wasm32-unknown-unknown`

Build WASM artifacts:

```bash
cd /home/shaun/retrochain-rc1/contracts/ra
cargo build --release --target wasm32-unknown-unknown
```

Artifacts will be under:

- `target/wasm32-unknown-unknown/release/ra_cw20.wasm`
- `target/wasm32-unknown-unknown/release/ra_converter.wasm`

## Deploy (high-level)

Recommended order (because converter must be the CW20 minter):

1. Store + instantiate `ra_cw20` with a temporary minter (e.g. deployer or governance).
2. Store + instantiate `ra_converter` with:
   - `native_denom = "uretro"`
   - `fee_collector_addr = <fee-collector bech32 addr>`
   - `ra_cw20_addr = <ra_cw20 contract addr>`
3. Call `ra_cw20` `UpdateMinter` to set the minter to the `ra_converter` contract address.

## Usage

- `Convert {}`
  - Anyone can call.
  - Must attach non-zero funds of `native_denom` (expected `uretro`).
  - Mints RA 1:1 to sender.

- `RewardMint { recipient }`
  - Only `operator` can call.
  - Must attach non-zero funds of `native_denom`.
  - Mints RA 1:1 to `recipient`.

- `UpdateOperator { operator }`
  - Only current operator can call.
