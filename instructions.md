# Instructions (RetroChain RC1)

These instructions are for making safe, consistent changes to RetroChain, with emphasis on the `x/arcade` module.

## Repo overview

- App wiring: `app/app_config.go` (runtime/depinject module config + ordering) and `app/app.go` (app construction + some manual keepers).
- Explorer-facing REST aliases: `app/api_routes.go` mounts `/api/*` helpers.
- Custom modules live under `x/` (notably `x/arcade`, `x/burn`, `x/retrochain`).

## Arcade development checklist

When adding/changing Arcade functionality, keep changes scoped and follow this order.

### 1) Define/extend protobufs

- Edit protobufs under `proto/retrochain/arcade/v1/`:
  - `tx.proto` for new `Msg*` and RPCs
  - `query.proto` for new query RPCs
  - `genesis.proto` for new persisted state
  - `params.proto` for new parameters
- Keep request/response messages stable and explicit.
- Prefer `uint64` for IDs/counters; prefer strings for addresses.

Regenerate:
- `make proto-gen`

Notes:
- Do not hand-edit generated Go code under `x/arcade/types` or generated TS client outputs.

### 2) Implement keeper state

- Keeper: `x/arcade/keeper/`
- Prefer `cosmossdk.io/collections` for KV state.
- Keep key layouts stable; treat keys as part of consensus.

Patterns to follow:
- Validate inputs early in the msg server (addresses, ranges, required fields).
- Emit events for explorer/UI consumption (keep names stable once shipped).
- Avoid floating point; use integers or SDK decimals (`math.LegacyDec`) if decimals are required.

### 3) Implement Msg server

- Implement/extend handlers in `x/arcade/keeper/msg_server*.go`.
- Use the module account / bank keeper correctly when minting/burning/transferring.
- Return deterministic results.

If mint/burn is required:
- Ensure `ModuleAccountPermission` includes the right permissions in `app/app_config.go`.

### 4) Implement Query server

- Implement/extend handlers in `x/arcade/keeper/query_server*.go`.
- Support pagination where list sizes can grow.
- Return consistent ordering (sorted by score/rank/time as intended).

### 5) Ensure module wiring stays correct

Arcade is manually instantiated in `app/app.go`, so changes often need extra care:

- Store keys: Arcade uses `arcademoduletypes.StoreKey` and `arcademoduletypes.MemStoreKey` created in `app/app.go`.
- App module registration: `x/arcade/module/module.go` registers Msg/Query services.
- Explorer routes: `/api/retrochain/arcade/v1/*` and `/api/arcade/v1/*` should expose new queries automatically via gRPC-Gateway.

If you add a new module (not just Arcade features), also update:
- `app/app_config.go` ordering lists and module config
- add an upgrade handler if introducing a new KV store key

### 6) Genesis & params

- If new state must exist at genesis, update Arcade genesis types and keeper `InitGenesis/ExportGenesis`.
- If behavior should be configurable, add params in `params.proto` and implement param accessors + validation.

Rules:
- Keep params backwards compatible where possible.
- Validate param ranges (avoid chain-halting values).

### 7) API compatibility (Explorer + frontend)

- REST broadcast requires `tx_bytes` (base64 `TxRaw`) at `POST /cosmos/tx/v1beta1/txs`.
- Arcade queries should be reachable under `/api/retrochain/arcade/v1/...` and `/api/arcade/v1/...`.

### 8) Testing & verification

Preferred quick checks:
- `go test ./... -run '^$'` (compile check)
- `go test ./x/arcade/...`
- `go build ./cmd/retrochaind`

If you change consensus state/key layouts:
- Add/extend unit tests adjacent to the keeper code you changed.

## Adding a brand new module (template)

1. Create `x/<name>` scaffold with:
   - `types` (module name/store key, codec/registration)
   - `keeper` (state + msg/query servers)
   - `module` (AppModule, service registration, genesis)
2. Wire it into `app/app_config.go`:
   - side-effect import
   - add to `BeginBlockers`/`EndBlockers`/`InitGenesis` as appropriate
   - add `ModuleConfig` entry
3. If adding a new KV store on an existing chain:
   - add an `upgrade` plan + store loader that includes the new store key
4. Build + compile-check.
