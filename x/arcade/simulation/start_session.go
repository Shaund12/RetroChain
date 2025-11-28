package simulation

import (
	"math/rand"

	"github.com/cosmos/cosmos-sdk/baseapp"
	"github.com/cosmos/cosmos-sdk/client"
	sdk "github.com/cosmos/cosmos-sdk/types"
	simtypes "github.com/cosmos/cosmos-sdk/types/simulation"
	"github.com/cosmos/cosmos-sdk/x/simulation"

	"retrochain/x/arcade/keeper"
	"retrochain/x/arcade/types"
)

// SimulateMsgStartSession simulates starting a new game session.
func SimulateMsgStartSession(
	ak types.AuthKeeper,
	bk types.BankKeeper,
	k keeper.Keeper,
	txGen client.TxConfig,
) simtypes.Operation {
	return func(r *rand.Rand, app *baseapp.BaseApp, ctx sdk.Context, accs []simtypes.Account, chainID string,
	) (simtypes.OperationMsg, []simtypes.FutureOperation, error) {
		simAccount, _ := simtypes.RandomAcc(r, accs)

		// List of game IDs to randomly select from
		gameIDs := []string{"space-raiders", "platform-hero", "puzzle-master", "racing-fury", "retro-fighter"}
		gameID := gameIDs[r.Intn(len(gameIDs))]

		msg := &types.MsgStartSession{
			Creator: simAccount.Address.String(),
			GameId:  gameID,
		}

		// Check if player has credits
		credits, err := k.GetPlayerCredits(ctx, simAccount.Address.String())
		if err != nil || credits == 0 {
			return simtypes.NoOpMsg(types.ModuleName, sdk.MsgTypeURL(msg), "player has no credits"), nil, nil
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
			CoinsSpentInMsg: sdk.NewCoins(),
		}

		return simulation.GenAndDeliverTxWithRandFees(txCtx)
	}
}
