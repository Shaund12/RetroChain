//go:build tokenfactory

package app

import (
	appv1alpha1 "cosmossdk.io/api/cosmos/app/v1alpha1"
	"cosmossdk.io/depinject/appconfig"

	_ "retrochain/x/tokenfactory/module"
	tokenfactorytypes "retrochain/x/tokenfactory/types"
)

func tokenfactoryModuleConfig() *appv1alpha1.ModuleConfig {
	return &appv1alpha1.ModuleConfig{
		Name:   tokenfactorytypes.ModuleName,
		Config: appconfig.WrapAny(&tokenfactorytypes.Module{}),
	}
}
