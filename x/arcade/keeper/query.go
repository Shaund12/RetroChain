package keeper

import (
	"retrochain/x/arcade/types"
)

type queryServer struct {
	k Keeper
	types.UnimplementedQueryServer
}

var _ types.QueryServer = (*queryServer)(nil)

// NewQueryServerImpl returns an implementation of the QueryServer interface
// for the provided Keeper.
func NewQueryServerImpl(k Keeper) types.QueryServer {
	return &queryServer{k: k}
}
