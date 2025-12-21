//go:build nftfactory

package app

import (
	appv1alpha1 "cosmossdk.io/api/cosmos/app/v1alpha1"
	"cosmossdk.io/depinject/appconfig"

	_ "retrochain/x/nftfactory/module"
	nftfactorytypes "retrochain/x/nftfactory/types"
)

func nftfactoryModuleConfig() *appv1alpha1.ModuleConfig {
	return &appv1alpha1.ModuleConfig{
		Name:   nftfactorytypes.ModuleName,
		Config: appconfig.WrapAny(&nftfactorytypes.Module{}),
	}
}
