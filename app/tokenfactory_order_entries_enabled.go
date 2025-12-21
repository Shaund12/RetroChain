//go:build tokenfactory

package app

import tokenfactorytypes "retrochain/x/tokenfactory/types"

func tokenfactoryOrderEntries() []string {
	return []string{tokenfactorytypes.ModuleName}
}
