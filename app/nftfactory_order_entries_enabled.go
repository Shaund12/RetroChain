//go:build nftfactory

package app

import nftfactorytypes "retrochain/x/nftfactory/types"

func nftfactoryOrderEntries() []string {
	return []string{nftfactorytypes.ModuleName}
}
