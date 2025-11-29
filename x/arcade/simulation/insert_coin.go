package simulation

import (
	"math/rand"

	"cosmossdk.io/math"
	"github.com/cosmos/cosmos-sdk/baseapp"
	"github.com/cosmos/cosmos-sdk/client"
	sdk "github.com/cosmos/cosmos-sdk/types"
	simtypes "github.com/cosmos/cosmos-sdk/types/simulation"
	"github.com/cosmos/cosmos-sdk/x/simulation"

	"retrochain/x/arcade/keeper"
	"retrochain/x/arcade/types"
)

// SimulateMsgInsertCoin simulates a user inserting coins to purchase credits.
func SimulateMsgInsertCoin(
	ak types.AuthKeeper,
	bk types.BankKeeper,
	k keeper.Keeper,
	txGen client.TxConfig,
) simtypes.Operation {
	return func(r *rand.Rand, app *baseapp.BaseApp, ctx sdk.Context, accs []simtypes.Account, chainID string,
	) (simtypes.OperationMsg, []simtypes.FutureOperation, error) {
		simAccount, _ := simtypes.RandomAcc(r, accs)

		// Generate random credits amount between 1 and 10
		credits := uint64(r.Intn(10) + 1)

		// List of game IDs to randomly select from
		gameIDs := []string{"space-raiders", "platform-hero", "puzzle-master", "racing-fury", "retro-fighter"}
		gameID := gameIDs[r.Intn(len(gameIDs))]

		msg := &types.MsgInsertCoin{
			Creator: simAccount.Address.String(),
			Credits: credits,
			GameId:  gameID,
		}

		// Check if account has enough balance
		spendable := bk.SpendableCoins(ctx, simAccount.Address)
		requiredAmount := sdk.NewCoin("uretro", math.NewInt(int64(credits*1000000)))
		if !spendable.IsAllGTE(sdk.NewCoins(requiredAmount)) {
			return simtypes.NoOpMsg(types.ModuleName, sdk.MsgTypeURL(msg), "insufficient balance for credits"), nil, nil
		}

		txCtx := simulation.OperationInput{
			R:               r,
			App:             app,
			TxGen:           txGen,
			Cdc:             nil,
			Msg:             msg,
			Context:         ctx,
			SimAccount:      simAccount,
			AccountKeeper:   ak,
			Bankkeeper:      bk,
			ModuleName:      types.ModuleName,
			CoinsSpentInMsg: sdk.NewCoins(requiredAmount),
		}

		return simulation.GenAndDeliverTxWithRandFees(txCtx)
	}
}
