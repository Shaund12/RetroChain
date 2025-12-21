//go:build !tokenfactory

package app

import appv1alpha1 "cosmossdk.io/api/cosmos/app/v1alpha1"

func tokenfactoryModuleConfig() *appv1alpha1.ModuleConfig {
	return nil
}
