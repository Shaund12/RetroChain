package keeper

import (
	"context"
	"errors"
	"strconv"

	"retrochain/x/arcade/types"

	"cosmossdk.io/collections"
	errorsmod "cosmossdk.io/errors"
	sdk "github.com/cosmos/cosmos-sdk/types"
)

// SubmitScore handles the SubmitScore message.
// It updates the score for an active game session.
func (k *msgServer) SubmitScore(ctx context.Context, msg *types.MsgSubmitScore) (*types.MsgSubmitScoreResponse, error) {
	if _, err := k.addressCodec.StringToBytes(msg.Creator); err != nil {
		return nil, errorsmod.Wrap(err, "invalid creator address")
	}

	// Get the game session
	session, err := k.GetSession(ctx, msg.SessionId)
	if err != nil {
		if errors.Is(err, collections.ErrNotFound) {
			return nil, errorsmod.Wrap(types.ErrNotFound, "session not found")
		}
		return nil, errorsmod.Wrap(err, "failed to get session")
	}

	// Check if the player is the owner of the session
	if session.Player != msg.Creator {
		return nil, errorsmod.Wrap(types.ErrUnauthorized, "only the session owner can submit scores")
	}

	// Check if the session is active
	if session.Status != types.SessionStatusActive {
		return nil, errorsmod.Wrap(types.ErrInvalidRequest, "session is not active")
	}

	// Update the session score
	session.CurrentScore = msg.Score

	// Store the updated session
	if err := k.SetSession(ctx, session); err != nil {
		return nil, errorsmod.Wrap(err, "failed to update session")
	}

	// Emit score updated event
	sdkCtx := sdk.UnwrapSDKContext(ctx)
	sdkCtx.EventManager().EmitEvent(
		sdk.NewEvent(
			types.EventScoreUpdated,
			sdk.NewAttribute(types.AttrSessionID, strconv.FormatUint(msg.SessionId, 10)),
			sdk.NewAttribute(types.AttrPlayer, msg.Creator),
			sdk.NewAttribute(types.AttrScore, strconv.FormatUint(msg.Score, 10)),
		),
	)

	return &types.MsgSubmitScoreResponse{}, nil
}
