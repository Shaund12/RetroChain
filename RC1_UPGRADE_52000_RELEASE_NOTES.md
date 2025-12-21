# 🎉 Woohoo — Upgrade Complete (RC1 @ height 52000)

This page is intended for explorers to display after the chain upgrade completes.

**Upgrade name:** `rc1-combined-v1`  
**Upgrade height:** `52000`

---

## What’s new

### 🔥 Burn module (fee burn)
- RetroChain now supports automatic fee burning via the `x/burn` module.
- Tokenomics update: the chain is configured to burn a portion of the `fee_collector` balance per block.

### 🧱 BTC Staking module (`x/btcstake`)
- The BTC staking module is now enabled.
- New query endpoints are available for explorers under the RetroChain API namespace.

### 🧠 CosmWasm smart contracts
- CosmWasm (`wasmd/x/wasm`) is enabled.
- Explorers and tooling can query CosmWasm params and state via standard CosmWasm REST/gRPC-Gateway routes.

### 🕹️ Arcade + Explorer API compatibility
- Explorer-friendly REST routing is supported v##
ia `/api/*` convenience paths.
- Arcade queries are compatible via both:
  - `/retrochain/arcade/v1/*`
  - `/arcade/v1/*` (alias)

---

## Explorer integration notes (quick)

- Tx search on SDK v0.53+ expects `query=`; some explorers send `events[]=`. RetroChain accepts both.
- CosmWasm params compatibility:
  - `/cosmwasm/wasm/v1/params` is supported (rewritten internally to the v0.53 wasmd params route).

---

## Where to verify

Common “green check” endpoints:
- Arcade params: `/api/arcade/v1/params`
- Burn params: `/api/retrochain/burn/v1/params`
- BTC stake params: `/api/retrochain/btcstake/v1/params`
- CosmWasm params: `/api/cosmwasm/wasm/v1/params`
- Recent txs: `/api/recent-txs?limit=5`

---

## For operators

- Manual upgrade deployments (no Cosmovisor) are supported.
- Full upgrade checklist + implementation notes live in `UPGRADE_PLAYBOOK.md`.
