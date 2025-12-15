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
	if msg == nil {
		return nil, errorsmod.Wrap(types.ErrInvalidRequest, "invalid message")
	}
	if _, err := k.addressCodec.StringToBytes(msg.Creator); err != nil {
		return nil, errorsmod.Wrap(err, "invalid creator address")
	}

	// Validate game_id is provided
	if msg.GameId == "" {
		return nil, errorsmod.Wrap(types.ErrInvalidRequest, "game_id is required")
	}

	params, err := k.getParams(ctx)
	if err != nil {
		return nil, errorsmod.Wrap(err, "failed to load params")
	}

	// Enforce max active sessions per player
	if params.MaxActiveSessions > 0 {
		sessions, err := k.ListActiveSessions(ctx)
		if err != nil {
			return nil, errorsmod.Wrap(err, "failed to check active sessions")
		}
		var activeForPlayer uint32
		for _, s := range sessions {
			if s.Player == msg.Creator {
				activeForPlayer++
			}
		}
		if activeForPlayer >= params.MaxActiveSessions {
			return nil, errorsmod.Wrap(types.ErrInvalidRequest, "max active sessions reached")
		}
	}

	// Determine credit cost based on registered game (defaults to 1)
	creditCost := uint64(1)
	if game, err := k.GetArcadeGame(ctx, msg.GameId); err == nil && game != nil {
		if game.CreditsPerPlay > 0 {
			creditCost = game.CreditsPerPlay
		}
	}

	credits, err := k.GetPlayerCredits(ctx, msg.Creator)
	if err != nil {
		return nil, errorsmod.Wrap(err, "failed to get player credits")
	}
	if credits < creditCost {
		return nil, errorsmod.Wrap(types.ErrInsufficientFund, "insufficient credits to start a session")
	}
	newCredits := credits - creditCost
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
	startTime := sdkCtx.BlockTime()

	// Create new game session
	startingLives := uint64(3)
	startingLevel := uint64(1)
	if msg.Difficulty > 0 {
		startingLevel = msg.Difficulty
	}

	session := types.GameSession{
		SessionId:         sessionID,
		GameId:            msg.GameId,
		Player:            msg.Creator,
		CreditsUsed:       creditCost,
		CurrentScore:      0,
		Level:             startingLevel,
		Lives:             startingLives,
		Status:            types.SessionStatusActive,
		StartTime:         &startTime,
		ComboMultiplier:   1,
		PowerUpsCollected: []string{},
		ContinuesUsed:     0,
	}

	// Store the session
	if err := k.SetSession(ctx, session); err != nil {
		return nil, errorsmod.Wrap(err, "failed to create session")
	}
	_ = k.maybeRecordQuickStart(ctx, msg.Creator, startTime)

	// Emit game started event
	sdkCtx.EventManager().EmitEvent(
		sdk.NewEvent(
			types.EventGameStarted,
			sdk.NewAttribute(types.AttrSessionID, strconv.FormatUint(sessionID, 10)),
			sdk.NewAttribute(types.AttrGameID, msg.GameId),
			sdk.NewAttribute(types.AttrPlayer, msg.Creator),
		),
	)

	if err := k.updateLeaderboard(ctx, msg.Creator, 0, 1, 0, 0, 0); err != nil {
		return nil, errorsmod.Wrap(err, "failed to update leaderboard")
	}

	return &types.MsgStartSessionResponse{SessionId: sessionID, StartingLives: startingLives, StartingLevel: startingLevel}, nil
}
