//go:build !nftfactory

package app

import (
	upgradetypes "cosmossdk.io/x/upgrade/types"

	dbm "github.com/cosmos/cosmos-db"
)

func (app *App) registerNftfactoryUpgradeHandler() {}

func (app *App) maybeSetNftfactoryStoreLoader(homeDir string, db dbm.DB, upgradeInfo upgradetypes.Plan) {
}
