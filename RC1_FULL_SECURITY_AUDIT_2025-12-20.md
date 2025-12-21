# RetroChain RC1 — Full Feature & Security Audit

Date: 2025-12-20

This report covers the current RetroChain RC1 codebase and the operational surfaces that materially affect safety: on-chain modules, upgrade/governance authority paths, IBC + CosmWasm wiring, and public node endpoints used by the explorer.

## 1) Executive Summary

RetroChain RC1 is a Cosmos SDK chain with custom economic/game modules (`x/arcade`, `x/btcstake`, `x/burn`, `x/tokenfactory`, `x/nftfactory`, `x/retrochain`) and an explorer-facing REST surface implemented via the SDK REST server + gRPC-gateway, plus a handful of custom compatibility routes.

The highest-impact issues identified during this audit were:

- Governance/authority enforcement: `x/btcstake` parameter updates required an explicit runtime authority check.
- Economic arithmetic safety: the arcade purchase flow and reward/stat aggregation had multiple integer overflow paths.
- Operational exposure: permissive CORS in templates (RPC wildcard, indexer API wildcard) and unbounded query gas limit were unsafe defaults.

All of the above were addressed in code/config changes and validated via repository compile checks.

## 2) Scope

### In scope
- App wiring: `app/app.go`, `app/app_config.go`, `app/ibc.go`, `app/api_routes.go`
- Custom modules: `x/arcade`, `x/btcstake`, `x/burn`, `x/tokenfactory`, `x/nftfactory`, `x/retrochain`
- Governance + upgrades: `x/upgrade` handler wiring and store loader behavior
- IBC: ICS-20 transfer, ICA host/controller, IBC routers
- CosmWasm: keeper wiring and node config ingestion
- Operational templates: `testnet/home/config/app.toml`, `testnet/home/config/config.toml`
- Explorer speed indexer read API: `tools/indexer_api.py`
- Hermes relayer config template: `tools/ibc/hermes/config.toml`

### Out of scope (not fully verified)
- Full production deployment architecture (firewalls, reverse proxy configs, WAF)
- Validator key-management procedures and host hardening
- Economic design review of tokenomics (supply schedules, inflation model)

## 3) System Overview (feature surface)

### Core chain stack
- Cosmos SDK app with depinject module wiring (`app/app.go`, `app/app_config.go`).
- IBC manually wired (IBC modules do not fully support depinject yet):
  - IBC core, transfer (v1 + v2 router), ICA host/controller, tendermint + solomachine light clients (`app/ibc.go`).
- CosmWasm enabled:
  - Wasm store key registered by app, `wasmkeeper.NewKeeper(...)` with `wasm.ReadNodeConfig(appOpts)` (`app/ibc.go`).
  - Defensive PreBlocker to set default wasm params if missing to prevent chain halt (`app/app.go`).

### Custom modules
- `x/tokenfactory`: permissionless denom creation for users; admin actions on denom; module account has mint/burn permissions.
- `x/nftfactory`: permissionless native NFT class creation + minting on top of `cosmossdk.io/x/nft` (custom tx surface).
- `x/btcstake`: vault-like staking module for an allowed denom (e.g., IBC WBTC denom), mints receipt denom `stwbtc`, rewards in `uretro`.
- `x/arcade`: credits, sessions, scores, leaderboards, achievements, tournaments.
- `x/burn`: burns proportions of fee collector balances each BeginBlock based on params.
- `x/retrochain`: chain-specific module (params/query surface).

### Explorer/API surface
- Standard SDK REST + gRPC-gateway enabled in `app.toml`.
- Custom compatibility routes are installed in `app/api_routes.go`:
  - Adds gRPC-gateway registrations for chain modules, wasm, and IBC query services.
  - Normalizes `/cosmos/tx/v1beta1/txs` query behavior for explorer compatibility.
  - Adds arcade global list endpoints (sessions/achievements/leaderboards/etc.) implemented via direct store iteration with caps.
  - Enforces request-size limits for wasm smart query helpers.

### Optional fast explorer indexer
- SQLite indexer (`tools/sql_indexer.py`) + read API (`tools/indexer_api.py`) to serve blocks/txs/events efficiently.

## 4) Threat Model

The audit prioritizes:
- Unauthorized governance/authority actions (parameter changes, admin ops).
- Economic exploits (underpaying, minting/burning mismatches, reward theft).
- Remote DoS and resource exhaustion (REST/RPC queries, store iteration, wasm queries).
- Operational exposure (public endpoint configs, CORS, gRPC-web, pprof, rate limits).
- Relayer operational integrity (Hermes config safety and reliability).

## 5) Findings & Status

Severity levels are contextual to a public chain where REST/RPC are internet-accessible.

### CRITICAL

#### C1 — `x/btcstake` UpdateParams authority not enforced at runtime (FIXED)
- Impact: unauthorized parameter changes (e.g., changing `AllowedDenom`) could enable theft/misaccounting depending on upstream signer enforcement.
- Fix: `x/btcstake/keeper/msg_server.go` now parses `req.Authority` via keeper `addressCodec` and compares the bytes to the keeper’s configured authority; rejects mismatch.
- Related: `x/btcstake/keeper/keeper.go` stores `addressCodec` and validates authority bytes on keeper construction.

#### C2 — Arcade credit purchase cost overflow (underpayment) (FIXED)
- Impact: user-controlled `credits` multiplied by `costPerCredit` previously risked uint overflow leading to wraparound and underpayment.
- Fix: `x/arcade/keeper/msg_server_insert_coin.go` now computes costs using `cosmossdk.io/math.Int` and rejects credit balance overflow.

#### C3 — App-side mempool disabled in template (FIXED)
- Impact: `testnet/home/config/app.toml` had `mempool.max-txs = -1`, which disables tx insertion for the SDK app-side mempool implementation (transactions would not enter mempool).
- Fix: set `max-txs = 5000` in the template.

### HIGH

#### H1 — Arcade reward/stat aggregation overflow (FIXED)
- Impact: unchecked uint64 arithmetic could wrap counters and distort payouts/leaderboard data.
- Fix: overflow checks added across arcade reward calculations and leaderboard accumulator updates.

#### H2 — `x/burn` ignored BurnCoins error (FIXED)
- Impact: silent failure to burn could cause supply accounting drift without visibility.
- Fix: `x/burn/keeper/keeper.go` now logs BurnCoins failures.

#### H3 — RPC wildcard CORS in template (FIXED for explorer allowlist)
- Impact: wildcard CORS enables any browser origin to call your RPC; increases exposure (CSRF-like browser abuse, easier bot scraping).
- Fix: `testnet/home/config/config.toml` now allowlists only:
  - `https://retrochain.ddns.net`
  - `http://retrochain.ddns.net`

#### H4 — Indexer read API wildcard CORS (FIXED)
- Impact: `Access-Control-Allow-Origin: *` on explorer read API invites broad browser abuse.
- Fix: `tools/indexer_api.py` now disables CORS by default and supports an explicit allowlist via `--cors-origins` or `INDEXER_API_CORS_ORIGINS`.

### MEDIUM

#### M1 — Unbounded REST/gRPC query gas limit (FIXED)
- Impact: `query-gas-limit = 0` allows unbounded query gas; can amplify REST/gRPC DoS.
- Fix: `testnet/home/config/app.toml` now sets `query-gas-limit = "10000000"`.

#### M2 — gRPC-web enabled + bind to 0.0.0.0 (RECOMMENDATION)
- Observed: `testnet/home/config/app.toml` has `[grpc-web].enable = true` and API binds `0.0.0.0`.
- Risk: gRPC-web is effectively a public browser API surface; if exposed directly on validators it increases attack surface.
- Recommendation:
  - Disable gRPC-web unless required.
  - If required, expose only via reverse proxy with TLS + strict CORS allowlist + rate limiting.

#### M3 — Custom arcade list endpoints iterate module stores (RECOMMENDATION)
- Observed: `app/api_routes.go` implements explorer endpoints by walking stores and sorting in-loop, with caps (`maxArcadeScan`, `maxListLimit`).
- Risk: still potentially heavy on busy nodes; worst-case repeated scanning can cause latency spikes.
- Recommendation:
  - Add indexed/paginated query endpoints in `x/arcade` (preferred), or
  - Maintain a bounded “recent items” list in keeper state for O(1) retrieval.

#### M4 — Hermes relayer uses third-party RPC/WS for Cosmos Hub (RECOMMENDATION)
- Observed: `tools/ibc/hermes/config.toml` uses public RPC/WS endpoints for `cosmoshub-4`.
- Risk: reliability issues (WS headers/events), rate limits, and operational instability; integrity is still protected by IBC proofs, but liveness suffers.
- Recommendation:
  - Use your own Cosmos Hub full node or a trusted paid provider for relayer endpoints.
  - Keep RetroChain endpoints local (`localhost`) as in the template.
  - Ensure `trusting_period` is safely below the chain’s unbonding period.

### LOW

#### L1 — Template duplication/formatting issues (FIXED)
- Observed: `testnet/home/config/app.toml` contained duplicate `[api]`/`[grpc]` tables.
- Fix: removed duplicates.

#### L2 — Telemetry disabled by default (RECOMMENDATION)
- Observed: `testnet/home/config/app.toml` telemetry is disabled.
- Recommendation: enable Prometheus and alerting in production.

## 6) Configuration & Operational Guidance (production)

### Endpoint exposure model (recommended)
- Validators should not expose RPC/REST/gRPC directly to the internet.
- Run a dedicated public API node (full node) behind a reverse proxy.

### CORS policy
- **CometBFT RPC**: keep `[rpc].cors_allowed_origins` as a strict allowlist. Avoid `"*"`.
- **Cosmos SDK REST**:
  - Keep `enabled-unsafe-cors = false` in `app.toml`.
  - Add strict CORS at your reverse proxy for `retrochain.ddns.net`.
- **Indexer API**: configure `INDEXER_API_CORS_ORIGINS` with the explorer domain; do not use wildcard outside dev.

### Resource limiting
- Keep `query-gas-limit` bounded (already set in template).
- Enforce reverse-proxy rate limiting for:
  - `/cosmos/tx/v1beta1/txs` (search-heavy)
  - wasm smart queries
  - any custom store-walking endpoints

### CosmWasm policy checks (operator checklist)
The wasm keeper reads node config via `wasm.ReadNodeConfig(appOpts)`. Verify your `app.toml` wasm section:
- Who can upload code (permissioned vs permissionless)
- Max wasm size / instantiation limits
- Contract query limits
- Whether to disable IBC wasm if not needed

(These are operator-configurable; they are not fully enumerated in this report without the active deployment `app.toml`.)

## 7) Verification Performed

- Repository build/compile checks after fixes:
  - `go test ./... -run '^$'`
- Python syntax check for indexer API:
  - `python3 -m py_compile tools/indexer_api.py`

## 8) What Changed During This Audit (implementation log)

Implemented hardening changes include:
- `x/btcstake`: runtime authority enforcement for `UpdateParams`; keeper now retains `addressCodec`.
- `x/btcstake`: propagate `TotalStaked.Set` errors instead of silently ignoring.
- `x/arcade`: big-int cost calculation for credit purchases; overflow guards for counters and reward math.
- `x/burn`: log failures when `BurnCoins` returns error.
- `testnet/home/config/app.toml`:
  - bounded `query-gas-limit`
  - removed duplicate `[api]/[grpc]` blocks
  - set `mempool.max-txs` to a non-disabled value
- `testnet/home/config/config.toml`: RPC CORS allowlist for `retrochain.ddns.net`.
- `tools/indexer_api.py`: CORS allowlist support; disabled by default.
- `x/nftfactory/types/query.pb.go`: fixed a duplicate `package` line that broke builds.

## 9) Next Steps (recommended)

If you want to push to “production ready”:
1. Decide which endpoints are truly required publicly (REST only vs REST+RPC vs REST+RPC+gRPC-web).
2. Place public endpoints behind a reverse proxy (TLS, CORS allowlist, rate limits).
3. Confirm wasm upload/instantiate policy in your deployed `app.toml`.
4. Add profiling/metrics dashboards and alerting.
5. Add targeted tests for:
   - `x/btcstake` UpdateParams authority rejection
   - arcade overflow rejection paths

---

If you want, this report can be extended into a “production threat model + runbook” covering firewall rules, reverse-proxy snippets, and recommended node roles (validator vs API node vs indexer node).