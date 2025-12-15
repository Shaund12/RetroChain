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

// EndSession handles ending a game session and distributing rewards.
// It validates the session ownership, marks it as completed, and rewards the player based on score.
func (k *msgServer) endSessionInternal(ctx context.Context, sessionID uint64, player string, finalScore uint64, finalLevel uint64) (*types.GameSession, error) {
	if _, err := k.addressCodec.StringToBytes(player); err != nil {
		return nil, errorsmod.Wrap(err, "invalid player address")
	}

	// Get the game session
	session, err := k.GetSession(ctx, sessionID)
	if err != nil {
		if errors.Is(err, collections.ErrNotFound) {
			return nil, errorsmod.Wrap(types.ErrNotFound, "session not found")
		}
		return nil, errorsmod.Wrap(err, "failed to get session")
	}

	// Check if the player is the owner of the session
	if session.Player != player {
		return nil, errorsmod.Wrap(types.ErrUnauthorized, "only the session owner can end the session")
	}

	// Check if the session is active
	if session.Status != types.SessionStatusActive {
		return nil, errorsmod.Wrap(types.ErrInvalidRequest, "session is not active")
	}

	params, err := k.getParams(ctx)
	if err != nil {
		return nil, errorsmod.Wrap(err, "failed to load params")
	}

	// Get current block time
	sdkCtx := sdk.UnwrapSDKContext(ctx)
	endTime := sdkCtx.BlockTime()

	// Update final score/level if provided
	if finalScore > session.CurrentScore {
		session.CurrentScore = finalScore
	}
	if finalLevel > 0 {
		session.Level = finalLevel
	}

	// Mark session as completed
	session.Status = types.SessionStatusCompleted
	session.EndTime = &endTime

	// Store the updated session
	if err := k.SetSession(ctx, session); err != nil {
		return nil, errorsmod.Wrap(err, "failed to update session")
	}

	// Calculate and distribute rewards based on score (arcade tokens)
	if session.CurrentScore > 0 {
		rewardAmount := (session.CurrentScore / 1000) * uint64(params.TokensPerThousandPoints)
		if rewardAmount > 0 {
			if err := k.updateLeaderboard(ctx, player, 0, 0, 0, 0, rewardAmount); err != nil {
				// Don't fail the session end if rewards fail - just log the event
				sdkCtx.EventManager().EmitEvent(
					sdk.NewEvent(
						"arcade.reward_failed",
						sdk.NewAttribute(types.AttrSessionID, strconv.FormatUint(sessionID, 10)),
						sdk.NewAttribute(types.AttrPlayer, player),
						sdk.NewAttribute("error", err.Error()),
					),
				)
			} else {
				sdkCtx.EventManager().EmitEvent(
					sdk.NewEvent(
						types.EventRewardDistributed,
						sdk.NewAttribute(types.AttrSessionID, strconv.FormatUint(sessionID, 10)),
						sdk.NewAttribute(types.AttrPlayer, player),
						sdk.NewAttribute(types.AttrRewardAmount, strconv.FormatUint(rewardAmount, 10)),
					),
				)
			}
		}
	}

	// Emit session ended event
	sdkCtx.EventManager().EmitEvent(
		sdk.NewEvent(
			types.EventSessionEnded,
			sdk.NewAttribute(types.AttrSessionID, strconv.FormatUint(sessionID, 10)),
			sdk.NewAttribute(types.AttrGameID, session.GameId),
			sdk.NewAttribute(types.AttrPlayer, player),
			sdk.NewAttribute(types.AttrScore, strconv.FormatUint(session.CurrentScore, 10)),
		),
	)

	// Check for high score event
	if session.CurrentScore >= 100000 {
		sdkCtx.EventManager().EmitEvent(
			sdk.NewEvent(
				types.EventHighScore,
				sdk.NewAttribute(types.AttrSessionID, strconv.FormatUint(sessionID, 10)),
				sdk.NewAttribute(types.AttrGameID, session.GameId),
				sdk.NewAttribute(types.AttrPlayer, player),
				sdk.NewAttribute(types.AttrScore, strconv.FormatUint(session.CurrentScore, 10)),
			),
		)
	}

	return &session, nil
}

// GameOver handles ending a session when the player loses (game over).
func (k *msgServer) gameOverInternal(ctx context.Context, sessionID uint64, player string) (*types.GameSession, error) {
	playerAddr, err := k.addressCodec.StringToBytes(player)
	if err != nil {
		return nil, errorsmod.Wrap(err, "invalid player address")
	}
	_ = playerAddr // validate address conversion

	// Get the game session
	session, err := k.GetSession(ctx, sessionID)
	if err != nil {
		if errors.Is(err, collections.ErrNotFound) {
			return nil, errorsmod.Wrap(types.ErrNotFound, "session not found")
		}
		return nil, errorsmod.Wrap(err, "failed to get session")
	}

	// Check if the player is the owner of the session
	if session.Player != player {
		return nil, errorsmod.Wrap(types.ErrUnauthorized, "only the session owner can end the session")
	}

	// Check if the session is active
	if session.Status != types.SessionStatusActive {
		return nil, errorsmod.Wrap(types.ErrInvalidRequest, "session is not active")
	}

	// Get current block time
	sdkCtx := sdk.UnwrapSDKContext(ctx)
	endTime := sdkCtx.BlockTime()

	// Mark session as game over
	session.Status = types.SessionStatusGameOver
	session.EndTime = &endTime

	// Store the updated session
	if err := k.SetSession(ctx, session); err != nil {
		return nil, errorsmod.Wrap(err, "failed to update session")
	}

	// Emit game over event
	sdkCtx.EventManager().EmitEvent(
		sdk.NewEvent(
			types.EventGameOver,
			sdk.NewAttribute(types.AttrSessionID, strconv.FormatUint(sessionID, 10)),
			sdk.NewAttribute(types.AttrGameID, session.GameId),
			sdk.NewAttribute(types.AttrPlayer, player),
			sdk.NewAttribute(types.AttrScore, strconv.FormatUint(session.CurrentScore, 10)),
		),
	)

	if _, err := k.upsertHighScore(ctx, session.GameId, session.Player, session.CurrentScore, session.Level, endTime); err == nil {
		_ = k.updateLeaderboard(ctx, session.Player, session.CurrentScore, 0, 0, 0, 0)
	}
	// Record high score and leaderboard totals
	if _, err := k.upsertHighScore(ctx, session.GameId, session.Player, session.CurrentScore, session.Level, endTime); err == nil {
		// ignore high score error; rewards handled above
	}
	if err := k.updateLeaderboard(ctx, session.Player, session.CurrentScore, 0, 0, 0, 0); err != nil {
		return nil, errorsmod.Wrap(err, "failed to update leaderboard")
	}

	return &session, nil
}
