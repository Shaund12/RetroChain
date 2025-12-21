//go:build !tokenfactory

package app

import (
	upgradetypes "cosmossdk.io/x/upgrade/types"

	dbm "github.com/cosmos/cosmos-db"
)

func (app *App) registerTokenfactoryUpgradeHandler() {}

func (app *App) maybeSetTokenfactoryStoreLoader(homeDir string, db dbm.DB, upgradeInfo upgradetypes.Plan) {
}
