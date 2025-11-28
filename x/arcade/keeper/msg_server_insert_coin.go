package keeper

import (
	"context"
	"strconv"

	"retrochain/x/arcade/types"

	errorsmod "cosmossdk.io/errors"
	"cosmossdk.io/math"
	sdk "github.com/cosmos/cosmos-sdk/types"
)

// InsertCoin handles the InsertCoin message.
// It transfers tokens from the player to the module and grants them credits.
func (k *msgServer) InsertCoin(ctx context.Context, msg *types.MsgInsertCoin) (*types.MsgInsertCoinResponse, error) {
	creatorAddr, err := k.addressCodec.StringToBytes(msg.Creator)
	if err != nil {
		return nil, errorsmod.Wrap(err, "invalid creator address")
	}

	// Validate credits is positive
	if msg.Credits == 0 {
		return nil, errorsmod.Wrap(types.ErrInvalidRequest, "credits must be greater than 0")
	}

	// Validate game_id is provided
	if msg.GameId == "" {
		return nil, errorsmod.Wrap(types.ErrInvalidRequest, "game_id is required")
	}

	// Calculate token cost (1000000 utoken per credit as per documentation)
	tokenCost := msg.Credits * 1000000
	coins := sdk.NewCoins(sdk.NewCoin("uretro", math.NewIntFromUint64(tokenCost)))

	// Check if player has sufficient spendable coins
	spendable := k.bankKeeper.SpendableCoins(ctx, creatorAddr)
	if !spendable.IsAllGTE(coins) {
		return nil, errorsmod.Wrap(types.ErrInsufficientFund, "insufficient tokens to purchase credits")
	}

	// Transfer tokens from player to module account
	if err := k.bankKeeper.SendCoinsFromAccountToModule(ctx, creatorAddr, types.ModuleName, coins); err != nil {
		return nil, errorsmod.Wrap(err, "failed to transfer tokens")
	}

	// Get current player credits
	currentCredits, err := k.GetPlayerCredits(ctx, msg.Creator)
	if err != nil {
		return nil, errorsmod.Wrap(err, "failed to get player credits")
	}

	// Add new credits
	newCredits := currentCredits + msg.Credits
	if err := k.SetPlayerCredits(ctx, msg.Creator, newCredits); err != nil {
		return nil, errorsmod.Wrap(err, "failed to set player credits")
	}

	// Emit event for credits insertion
	sdkCtx := sdk.UnwrapSDKContext(ctx)
	sdkCtx.EventManager().EmitEvent(
		sdk.NewEvent(
			"arcade.credits_inserted",
			sdk.NewAttribute(types.AttrPlayer, msg.Creator),
			sdk.NewAttribute(types.AttrGameID, msg.GameId),
			sdk.NewAttribute("credits_purchased", strconv.FormatUint(msg.Credits, 10)),
			sdk.NewAttribute("total_credits", strconv.FormatUint(newCredits, 10)),
		),
	)

	return &types.MsgInsertCoinResponse{}, nil
}
