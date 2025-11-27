package keeper

import (
	"context"
	"encoding/json"
	
	"github.com/cosmos/cosmos-sdk/codec"
)

// InitGenesis initializes the module state from genesis.
func (k Keeper) InitGenesis(ctx context.Context, cdc codec.JSONCodec, data json.RawMessage) {
	// TODO: unmarshal genesis and populate stores
}

// ExportGenesis exports the module state to genesis.
func (k Keeper) ExportGenesis(ctx context.Context, cdc codec.JSONCodec) json.RawMessage {
	// TODO: export state
	return nil
}
