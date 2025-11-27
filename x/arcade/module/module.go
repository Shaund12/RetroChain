package module

import (
	"cosmossdk.io/depinject"
	"github.com/cosmos/cosmos-sdk/codec"
	"github.com/cosmos/cosmos-sdk/runtime"
	storetypes "github.com/cosmos/cosmos-sdk/store/types"
	"github.com/cosmos/cosmos-sdk/types/module"
	paramstypes "github.com/cosmos/cosmos-sdk/x/params/types"

	"retrochain/x/arcade/keeper"
	"retrochain/x/arcade/types"
)

// ProvideModule is used by depinject to construct the keeper and register store keys.
type ModuleInputs struct {
	depinject.In

	Cdc    codec.Codec
	Config *types.Module
	Params paramstypes.Subspace
}

type ModuleOutputs struct {
	depinject.Out

	Keeper keeper.Keeper
	Module module.AppModule
}

func ProvideModule(in ModuleInputs) ModuleOutputs {
	storeKey := storetypes.NewKVStoreKey(types.StoreKey)
	memKey := storetypes.NewMemoryStoreKey(types.MemStoreKey)

	k := keeper.NewKeeper(in.Cdc, storeKey, memKey, in.Params)

	// Register store keys via runtime module; services will be registered when generated code exists.
	m := runtime.NewAppModule("arcade", nil, nil)

	return ModuleOutputs{Keeper: k, Module: m}
}
