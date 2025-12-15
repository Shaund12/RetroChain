# Copilot guidance (RetroChain RC1)

This repo is a Cosmos SDK v0.53+ chain with custom modules under `x/`.

## What matters most

- **Denom**: use `uretro` as the base denom (6 decimals). Avoid introducing `stake` anywhere.
- **SDK version**: prefer v0.53 idioms (runtime/depinject wiring, `cosmossdk.io/math.LegacyDec`, `cosmossdk.io/collections`).
- **Explorer/API expectations**: explorer calls are expected to work via REST + gRPC-Gateway, including the convenience `/api/*` routes.

## Do/Don’t

- Do **edit protobufs** under `proto/` and regenerate (`make proto-gen`) rather than editing generated Go/TS files.
- Do **keep module wiring deterministic** by updating the ordered lists in `app/app_config.go` when a new module is added.
- Do **add an upgrade handler** when introducing a new store key to an existing network.
- Don’t change public API routes or prefixes unless explicitly requested.
- Don’t add new UX/features beyond the user’s request.

## App wiring (important)

RetroChain uses **both**:
- **DePinject/runtime** wiring via `app/app_config.go` + `app/app.go` (`runtime.AppBuilder`).
- **Manual registration** for certain modules/keepers (notably `x/arcade` and `x/burn`) created in `app/app.go`.

When adding a new `x/` module, you typically must:
1. Ensure the module has a `types.ModuleName` and `types.StoreKey`.
2. Import the module for side-effects in `app/app_config.go` (e.g. `_ "retrochain/x/<name>/module"`).
3. Add it to `runtimev1alpha1.Module` ordering lists:
   - `PreBlockers` / `BeginBlockers` / `EndBlockers` (as applicable)
   - `InitGenesis`
4. Add a `ModuleConfig` entry in `appConfig`.
5. If the module introduces a new KV store on an existing chain, add an **upgrade plan**:
   - The current retrochain store-key upgrade plan name is `rc1-retrochain-v1` (see `app/app.go`).

## Arcade module notes

- Arcade’s gRPC query service is exposed through gRPC-Gateway.
- Convenience routes are mounted in `app/api_routes.go`:
  - `/api/retrochain/arcade/v1/*`
  - `/api/arcade/v1/*` (alias)
  - `/api/recent-txs`

If you add new Arcade queries, they should be reachable via those `/api/...` paths.

## Broadcasting transactions (explorer/frontend)

The REST broadcast endpoint (`POST /cosmos/tx/v1beta1/txs`) expects a body with `tx_bytes` (base64-encoded `TxRaw`). If `tx_bytes` is missing/empty, the node returns HTTP 400 with `invalid empty tx`.

## Build/install conventions

- Preferred reproducible build: `go build -o build/retrochaind ./cmd/retrochaind`
- Preferred local install: `make install` (uses `go install` with ldflags).

## Quick verification

After changes:
- `go test ./... -run '^$'` (compile check)
- `go build ./cmd/retrochaind`
