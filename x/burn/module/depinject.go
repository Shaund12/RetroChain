package module

import (
	"cosmossdk.io/core/appmodule"
	"cosmossdk.io/core/store"
	"cosmossdk.io/depinject"
	"cosmossdk.io/depinject/appconfig"
	"github.com/cosmos/cosmos-sdk/codec"
	bankkeeper "github.com/cosmos/cosmos-sdk/x/bank/keeper"

	"retrochain/x/burn/keeper"
	"retrochain/x/burn/types"
)

var _ depinject.OnePerModuleType = AppModule{}

// IsOnePerModuleType implements the depinject.OnePerModuleType interface.
func (AppModule) IsOnePerModuleType() {}

func init() {
	appconfig.Register(
		&types.Module{},
		appconfig.Provide(ProvideModule),
	)
}

type ModuleInputs struct {
	depinject.In

	Config       *types.Module
	StoreService store.KVStoreService
	Cdc          codec.Codec
	BankKeeper   bankkeeper.Keeper
}

type ModuleOutputs struct {
	depinject.Out

	BurnKeeper keeper.Keeper
	Module     appmodule.AppModule
}

func ProvideModule(in ModuleInputs) ModuleOutputs {
	_ = in.Config // currently no module config fields
	k := keeper.NewKeeper(in.StoreService, in.Cdc, in.BankKeeper)
	m := NewAppModule(k)
	return ModuleOutputs{BurnKeeper: k, Module: m}
}
