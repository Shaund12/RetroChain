package keeper

import (
	"context"
	"strconv"

	"retrochain/x/arcade/types"

	errorsmod "cosmossdk.io/errors"
	sdk "github.com/cosmos/cosmos-sdk/types"
)

// StartSession handles the StartSession message.
// It creates a new game session for the player if they have sufficient credits.
func (k *msgServer) StartSession(ctx context.Context, msg *types.MsgStartSession) (*types.MsgStartSessionResponse, error) {
	if _, err := k.addressCodec.StringToBytes(msg.Creator); err != nil {
		return nil, errorsmod.Wrap(err, "invalid creator address")
	}

	// Validate game_id is provided
	if msg.GameId == "" {
		return nil, errorsmod.Wrap(types.ErrInvalidRequest, "game_id is required")
	}

	// Get player credits
	credits, err := k.GetPlayerCredits(ctx, msg.Creator)
	if err != nil {
		return nil, errorsmod.Wrap(err, "failed to get player credits")
	}

	// Check if player has at least 1 credit to start a session
	if credits == 0 {
		return nil, errorsmod.Wrap(types.ErrInsufficientFund, "insufficient credits to start a session")
	}

	// Deduct 1 credit for starting the session
	newCredits := credits - 1
	if err := k.SetPlayerCredits(ctx, msg.Creator, newCredits); err != nil {
		return nil, errorsmod.Wrap(err, "failed to deduct credits")
	}

	// Generate next session ID
	sessionID, err := k.NextSessionID(ctx)
	if err != nil {
		return nil, errorsmod.Wrap(err, "failed to generate session ID")
	}

	// Get current block time (deterministic across all nodes)
	sdkCtx := sdk.UnwrapSDKContext(ctx)
	startTime := sdkCtx.BlockTime().Unix()

	// Create new game session
	session := types.GameSession{
		SessionID:    sessionID,
		GameID:       msg.GameId,
		Player:       msg.Creator,
		CreditsUsed:  1,
		CurrentScore: 0,
		Status:       types.SessionStatusActive,
		StartTime:    startTime,
		EndTime:      0,
	}

	// Store the session
	if err := k.SetSession(ctx, session); err != nil {
		return nil, errorsmod.Wrap(err, "failed to create session")
	}

	// Emit game started event
	sdkCtx.EventManager().EmitEvent(
		sdk.NewEvent(
			types.EventGameStarted,
			sdk.NewAttribute(types.AttrSessionID, strconv.FormatUint(sessionID, 10)),
			sdk.NewAttribute(types.AttrGameID, msg.GameId),
			sdk.NewAttribute(types.AttrPlayer, msg.Creator),
		),
	)

	return &types.MsgStartSessionResponse{}, nil
}
