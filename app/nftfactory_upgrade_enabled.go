//go:build nftfactory

package app

import (
	"context"

	storetypes "cosmossdk.io/store/types"
	upgradetypes "cosmossdk.io/x/upgrade/types"

	dbm "github.com/cosmos/cosmos-db"
	sdk "github.com/cosmos/cosmos-sdk/types"
	"github.com/cosmos/cosmos-sdk/types/module"

	nftfactorytypes "retrochain/x/nftfactory/types"
)

func (app *App) registerNftfactoryUpgradeHandler() {
	app.UpgradeKeeper.SetUpgradeHandler(nftfactoryUpgradeName, func(ctx context.Context, plan upgradetypes.Plan, vm module.VersionMap) (module.VersionMap, error) {
		sdkCtx := sdk.UnwrapSDKContext(ctx)
		if err := app.clawbackMistakenFunds(sdkCtx); err != nil {
			return vm, err
		}
		return app.ModuleManager.RunMigrations(ctx, app.Configurator(), vm)
	})
}

func (app *App) maybeSetNftfactoryStoreLoader(homeDir string, db dbm.DB, upgradeInfo upgradetypes.Plan) {
	if upgradeInfo.Name != nftfactoryUpgradeName {
		return
	}
	if app.UpgradeKeeper.IsSkipHeight(upgradeInfo.Height) {
		return
	}

	storeUpgrades := storetypes.StoreUpgrades{Added: filterMissingStores(homeDir, db, []string{nftfactorytypes.StoreKey})}
	if len(storeUpgrades.Added) > 0 {
		app.SetStoreLoader(upgradetypes.UpgradeStoreLoader(upgradeInfo.Height, &storeUpgrades))
	}
}
