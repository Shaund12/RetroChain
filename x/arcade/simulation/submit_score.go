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

// SimulateMsgSubmitScore simulates submitting a score for an active game session.
func SimulateMsgSubmitScore(
	ak types.AuthKeeper,
	bk types.BankKeeper,
	k keeper.Keeper,
	txGen client.TxConfig,
) simtypes.Operation {
	return func(r *rand.Rand, app *baseapp.BaseApp, ctx sdk.Context, accs []simtypes.Account, chainID string,
	) (simtypes.OperationMsg, []simtypes.FutureOperation, error) {
		simAccount, _ := simtypes.RandomAcc(r, accs)

		// Generate a random score between 100 and 100000
		score := uint64(r.Intn(100000) + 100)

		// Use session ID 0 as a placeholder - in real simulation we'd track active sessions
		sessionID := uint64(0)

		msg := &types.MsgSubmitScore{
			Creator:   simAccount.Address.String(),
			SessionId: sessionID,
			Score:     score,
		}

		// Try to get the session to verify it exists and belongs to the player
		session, err := k.GetSession(ctx, sessionID)
		if err != nil {
			return simtypes.NoOpMsg(types.ModuleName, sdk.MsgTypeURL(msg), "no active session found"), nil, nil
		}

		if session.Player != simAccount.Address.String() {
			return simtypes.NoOpMsg(types.ModuleName, sdk.MsgTypeURL(msg), "session belongs to different player"), nil, nil
		}

		if session.Status != types.SessionStatusActive {
			return simtypes.NoOpMsg(types.ModuleName, sdk.MsgTypeURL(msg), "session is not active"), nil, nil
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
