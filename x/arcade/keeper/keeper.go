package keeper

import (
	"github.com/cosmos/cosmos-sdk/codec"
	storetypes "github.com/cosmos/cosmos-sdk/store/types"
	paramstypes "github.com/cosmos/cosmos-sdk/x/params/types"
)

// Keeper defines the arcade module keeper.
// Fill dependencies (bank, auth) as needed when implementing business logic.
type Keeper struct {
	cdc         codec.Codec
	storeKey    storetypes.StoreKey
	memKey      storetypes.StoreKey
	paramSpace  paramstypes.Subspace
}

func NewKeeper(cdc codec.Codec, storeKey, memKey storetypes.StoreKey, ps paramstypes.Subspace) Keeper {
	return Keeper{cdc: cdc, storeKey: storeKey, memKey: memKey, paramSpace: ps}
}
