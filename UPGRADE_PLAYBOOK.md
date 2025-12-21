\yu7RetroChain Upgrades Playbook (for Copilot + humans)juiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiii

This repo is a Cosmos SDK v0.53+ chain (`retrochaind`). Upgrades are managed via `x/upgrade` and are wired in `app/app.go`.

The goal of this doc is twofold:
- **How to add a new upgrade** in this codebase (correctly and safely).
- **What changed in the RC1 upgrade at height 52000**, including the fixes that made it succeed.

---

## Where upgrades live

- Upgrade wiring: `app/app.go` (`setupUpgradeHandlers`)
- Upgrade plan submission examples: `COSMOS_COMMANDS.md` ("Software upgrade proposal")
- General agent rules: `agents.md`, `copilot.md`

---

## RC1 upgrade (what happened)

Explorer-facing announcement text (copy/paste): `RC1_UPGRADE_52000_RELEASE_NOTES.md`.

### Upgrade plan applied

- Upgrade name: `rc1-combined-v1`
- Upgrade height: `52000`
- Code location: `app/app.go`

### Other upgrade plans in code

- `rc1-tokenfactory-v1`: adds the `tokenfactory` store key so factory denoms (and mint/burn) work
- `rc1-nftfactory-v1`: adds the `nftfactory` store key so users can create/mint native NFTs via txs


### Stores/modules enabled

At the upgrade height the chain enabled (and/or ensured) stores for:
- `wasm` (CosmWasm) — `wasmtypes.StoreKey`
- `burn` — `burntypes.StoreKey`
- `btcstake` — `btcstaketypes.StoreKey`
- `retrochain` — `retrochaintypes.StoreKey`

### Tokenomics change

The upgrade sets burn params (in the upgrade handler) so the burn module targets inflation control:
- burns a portion of the `fee_collector` balance per block

(Implementation: `setBurnTokenomicsParams` in `app/app.go`.)

### Two critical fixes required for a clean upgrade

1) **Store-loader safety (initial version mismatch)**

Symptom:
- `panic: failed to load store: initial version set to 52000, but found earlier version 1`

Root cause:
- The store-loader was treating some stores as newly `Added` at height 52000 even though the store already existed in the on-disk state.

Fix:
- The store upgrade logic now only includes a store in `StoreUpgrades.Added` if it is **actually missing in the current commit-info** (rootmulti `s/<latest>`).
- Filesystem checks alone are not reliable; the definitive source is the app DB’s commit-info.

2) **`fee_collector` missing burner permission**

Symptom:
- `panic: module account fee_collector does not have permissions to burn tokens: unauthorized`

Root cause:
- The pre-upgrade chain state had a `fee_collector` module account without the `burner` permission, but `x/burn` burns from `fee_collector` in `BeginBlock`.

Fix:
- The upgrade handler now ensures the on-chain `fee_collector` module account has `authtypes.Burner` permission before burn logic executes.

---

## How to add a new upgrade (checklist)

### 1) Decide upgrade name and scope

- Pick a stable upgrade name (string constant) and document it.
- Decide what the upgrade does:
  - Add new store keys (new modules)
  - Run module migrations
  - One-time state fix/migration
  - Module-account permission fixes
  - Parameter changes

Where to put the name:
- `app/app.go` as a `const` next to existing upgrade names.

### 2) If you add a new KV store: wire store upgrades

Rule:
- If you introduce a new store key on an existing network, you **must** add a store loader upgrade.

Implementation location:
- `app/app.go` → `setupUpgradeHandlers`

What to do:
- Create a `storetypes.StoreUpgrades{Added: []string{<store key>}}`
- Set store loader for the upgrade height:
  - `app.SetStoreLoader(upgradetypes.UpgradeStoreLoader(upgradeInfo.Height, &storeUpgrades))`

Important safety rule (RetroChain-specific):
- Only include store keys in `Added` if the store does not already exist in the DB commit-info.
  - This prevents the `initial version set to ... but found earlier version ...` panic.

### 3) Add an upgrade handler

Implementation location:
- `app/app.go` → `app.UpgradeKeeper.SetUpgradeHandler(<name>, ...)`

Typical pattern:
- Run any one-time state fixes first
- Then call:
  - `app.ModuleManager.RunMigrations(ctx, app.Configurator(), vm)`

### 4) Handle module accounts explicitly when needed

If your new logic burns/mints/sends from module accounts, ensure the state has correct permissions.

Common gotcha:
- Existing chains may have module accounts created under older permission sets.

Recommended pattern:
- In the upgrade handler, load the module account from state and rewrite it with required permissions.

RC1 example:
- Ensure `fee_collector` has `authtypes.Burner`.

### 5) Wire the module into the app (if new module)

- `app/app_config.go`
  - side-effect import: `_ "retrochain/x/<module>/module"`
  - ordering lists (`BeginBlockers`/`EndBlockers`/`InitGenesis` etc)
  - module `ModuleConfig`
- `app/app.go`
  - ensure keepers exist (depinject or manual)
  - ensure store keys are mounted (if manual wiring)

### 6) Verify compilation and build

From repo root:

```bash
go test ./... -run '^$'
go build -o build/retrochaind ./cmd/retrochaind
sha256sum build/retrochaind | tee build/retrochaind.sha256
```

### 7) Dry-run upgrade on a copy of data

Best practice:
- Never test the upgrade on your only copy of `~/.retrochain`.
- Work from a copy or snapshot.

### 8) Upgrade success criteria (minimum)

- Node starts and completes upgrade handler at the target height.
- No panics during `BeginBlock` (especially from new modules).
- API surfaces expected by explorers still work (see `EXPLORER_INTEGRATION.md`).

---

## Manual upgrade runbook (no Cosmovisor)

High-level flow:
1. Stop node at/near the upgrade height (validator coordination).
2. Replace `/usr/local/bin/retrochaind` with the new binary.
3. Restart node and confirm it logs `applying upgrade "<name>" at height: <height>`.

Example binary swap (same machine):

```bash
sudo systemctl stop retrochaind 2>/dev/null || true
sudo cp -a /usr/local/bin/retrochaind /usr/local/bin/retrochaind.bak.$(date +%Y%m%d-%H%M%S)
sudo install -m 0755 ./build/retrochaind /usr/local/bin/retrochaind
/usr/local/bin/retrochaind version
sudo systemctl start retrochaind 2>/dev/null || true
```

---

## RC1 nftfactory upgrade (native NFT deployment)

- Upgrade name: `rc1-nftfactory-v1`
- Post-upgrade binary must be built with: `-tags nftfactory`
- Recommended (if TokenFactory is already live): build with both tags so both modules remain enabled:

```bash
go build -tags "tokenfactory,nftfactory" -o build/retrochaind ./cmd/retrochaind
sha256sum build/retrochaind | tee build/retrochaind.sha256
```

Proposal submission helper:
- `submit-rc1-nftfactory-v1.sh` (uses `contracts/ra/deploy/proposal_upgrade_rc1_nftfactory_v1.json`)

Notes on “Interchain Security (ICS)” for RC1:
- This repo currently includes IBC core + ICS-20 transfer + ICA (ibc-go v10).
- Cosmos “Interchain Security” (CCV consumer/provider) modules are *not* currently vendored/wired (no `interchain-security` / `ccv` deps in `go.mod`), so adding ICS is a separate, larger integration (new modules + new consensus/security assumptions + cross-chain coordination).

---

## Notes for Copilot (what to avoid)

- Do **not** call module gRPC QueryServers directly from HTTP handlers (SDK context injection will be missing). Use gRPC-Gateway registration.
- If you add a store key to an existing network, always add an upgrade handler + store loader.
- Prefer modifying `proto/` and regenerating code over editing generated code.
- Keep base denom as `uretro`.
