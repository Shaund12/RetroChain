# Agents (RetroChain RC1)

This file is guidance for automated agents working in this repo.

## Operating rules

- Default to the smallest possible change set; do not add “nice to haves”.
- Prefer modifying `proto/` and regenerating code over editing generated code.
- Keep the chain base denom as `uretro`.
- When introducing a new store key for an existing chain, add an upgrade handler.

## Workflow (recommended)

1. Locate the relevant module/app wiring first
   - App wiring: `app/app_config.go`, `app/app.go`
   - Explorer routes: `app/api_routes.go`
   - Module code: `x/<module>/...`
2. Make code changes.
3. Verify compilation:
   - `go test ./... -run '^$'`
4. Build the binary:
   - `go build -o build/retrochaind ./cmd/retrochaind`
5. If asked to “install”:
   - `make install` (installs `retrochaind` into `$GOBIN`/`$GOPATH/bin`)

## Common checklists

### Adding or wiring a module

- `app/app_config.go`
  - side-effect import for the module’s `module` package
  - added to `BeginBlockers`/`EndBlockers`/`InitGenesis` if required
  - added `ModuleConfig` entry
- `app/app.go`
  - keeper is injected (depinject) OR manually instantiated (like Arcade)
  - if manual: store keys created and keeper is created before `appBuilder.Build()`
- Upgrade
  - upgrade plan + store loader includes the new store key

### Explorer/API compatibility

- gRPC-Gateway routes for Arcade should work via:
  - `/api/retrochain/arcade/v1/*`
  - `/api/arcade/v1/*`
- REST broadcast:
  - `POST /cosmos/tx/v1beta1/txs` must include `tx_bytes` (base64 `TxRaw`) or it returns `invalid empty tx`.

## Runbook (local)

- Install binary: `make install`
- Build local binary artifact: `go build -o build/retrochaind ./cmd/retrochaind`
- Start dev node (if Ignite is configured): `ignite chain serve`

Ports commonly used:
- RPC: `26657`
- REST: `1317`
- gRPC: `9090`
- WS: `26657/websocket`
