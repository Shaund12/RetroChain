package keeper

import (
    "context"

    "retrochain/x/arcade/types"
)

// InitGenesis is intentionally minimal/no-op for now.
// It does NOT touch any KV stores, so the chain can boot
// even if the arcade store key isn't fully wired.
func (k Keeper) InitGenesis(ctx context.Context, genState types.GenesisState) error {
    // If you really want to store params later, you'll need to:
    // - Wire the arcade KVStoreKey into the app's multistore in app/app.go
    // - Then safely call k.Params.Set(ctx, ...) here.
    return nil
}

// ExportGenesis returns a default/empty genesis for the arcade module.
// Also does NOT touch KV stores.
func (k Keeper) ExportGenesis(ctx context.Context) (*types.GenesisState, error) {
    // Use DefaultGenesis so the JSON shape is correct.
    genesis := types.DefaultGenesis()
    return genesis, nil
}
