//go:build tokenfactory

package app

import (
	"context"

	storetypes "cosmossdk.io/store/types"
	upgradetypes "cosmossdk.io/x/upgrade/types"

	dbm "github.com/cosmos/cosmos-db"
	"github.com/cosmos/cosmos-sdk/types/module"

	tokenfactorytypes "retrochain/x/tokenfactory/types"
)

func (app *App) registerTokenfactoryUpgradeHandler() {
	app.UpgradeKeeper.SetUpgradeHandler(tokenfactoryUpgradeName, func(ctx context.Context, plan upgradetypes.Plan, vm module.VersionMap) (module.VersionMap, error) {
		return app.ModuleManager.RunMigrations(ctx, app.Configurator(), vm)
	})
}

func (app *App) maybeSetTokenfactoryStoreLoader(homeDir string, db dbm.DB, upgradeInfo upgradetypes.Plan) {
	if upgradeInfo.Name != tokenfactoryUpgradeName {
		return
	}
	if app.UpgradeKeeper.IsSkipHeight(upgradeInfo.Height) {
		return
	}

	storeUpgrades := storetypes.StoreUpgrades{Added: filterMissingStores(homeDir, db, []string{tokenfactorytypes.StoreKey})}
	if len(storeUpgrades.Added) > 0 {
		app.SetStoreLoader(upgradetypes.UpgradeStoreLoader(upgradeInfo.Height, &storeUpgrades))
	}
}
