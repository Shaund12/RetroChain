# ra_claimdrop

A minimal **free-for-all** claim contract for **native** coins (e.g. `uretro`).

## What it does

- Fixed claim amount per address (e.g. `2500 RETRO` = `2_500_000_000 uretro`).
- Total cap (e.g. `1_000_000 RETRO` = `1_000_000_000_000 uretro`).
- First-come-first-served.
- Each RetroChain address can claim once.

## Important note

This design is intentionally simple and is **not sybil-resistant**: anyone can generate many new addresses and drain the pool.

If you want “free-for-all but only for real Vitruveo users”, you’ll need some gating mechanism (allowlist, signature, NFT/LP/stake check, etc.).

## Build

```bash
cd contracts/ra
cargo test -p ra_claimdrop
```

(For chain deployment you’d build a wasm artifact using your normal CosmWasm build flow.)
