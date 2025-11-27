package keeper

import (
	"github.com/cosmos/cosmos-sdk/codec"
	"github.com/cosmos/cosmos-sdk/types/module"
	"retrochain/x/arcade/types"
)

// InitGenesis sets default params and imports genesis state.
func (k Keeper) InitGenesis(ctx module.Context, cdc codec.JSONCodec, data json.RawMessage) {
	// TODO: unmarshal genesis and populate KV stores for games, tournaments, etc.
	// Set default params
	p := types.DefaultParams()
	_ = p.Validate()
	// when param subspace is fully wired, set params here
}

// ExportGenesis exports current module state.
func (k Keeper) ExportGenesis(ctx module.Context, cdc codec.JSONCodec) json.RawMessage {
	// TODO: marshal current state (params, games, tournaments, achievements, leaderboard)
	return nil
}
