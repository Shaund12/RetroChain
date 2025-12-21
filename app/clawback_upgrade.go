package app

import (
	"context"

	upgradetypes "cosmossdk.io/x/upgrade/types"

	"github.com/cosmos/cosmos-sdk/types"
	"github.com/cosmos/cosmos-sdk/types/bech32"
	"github.com/cosmos/cosmos-sdk/types/module"
)

const (
	// clawbackFromAddress is the account that received the mistaken funds.
	clawbackFromAddress = "cosmos17fyfhk7pjg0twcpvgu7ngm0ugzk7tl85efmcn5"
	// clawbackToAddress is the intended foundation destination (key name: foundation_validator).
	clawbackToAddress = "cosmos1fscvf7rphx477z6vd4sxsusm2u8a70kewvc8wy"
)

func (app *App) clawbackMistakenFunds(ctx types.Context) error {
	_, fromBz, err := bech32.DecodeAndConvert(clawbackFromAddress)
	if err != nil {
		return err
	}
	_, toBz, err := bech32.DecodeAndConvert(clawbackToAddress)
	if err != nil {
		return err
	}

	from := types.AccAddress(fromBz)
	to := types.AccAddress(toBz)

	balances := app.BankKeeper.GetAllBalances(ctx, from)
	if balances.IsZero() {
		return nil
	}

	ctx.Logger().Info(
		"clawback: moving balances",
		"from", clawbackFromAddress,
		"to", clawbackToAddress,
		"amount", balances.String(),
	)

	return app.BankKeeper.SendCoins(ctx, from, to, balances)
}

func (app *App) registerClawbackUpgradeHandler() {
	app.UpgradeKeeper.SetUpgradeHandler(clawbackUpgradeName, func(ctx context.Context, plan upgradetypes.Plan, vm module.VersionMap) (module.VersionMap, error) {
		sdkCtx := types.UnwrapSDKContext(ctx)
		if err := app.clawbackMistakenFunds(sdkCtx); err != nil {
			return vm, err
		}

		return app.ModuleManager.RunMigrations(ctx, app.Configurator(), vm)
	})
}
