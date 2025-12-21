//go:build !nftfactory

package app

import appv1alpha1 "cosmossdk.io/api/cosmos/app/v1alpha1"

func nftfactoryModuleConfig() *appv1alpha1.ModuleConfig {
	return nil
}
