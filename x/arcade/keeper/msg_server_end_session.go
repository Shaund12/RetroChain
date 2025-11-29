package keeper

import (
	"context"
	"errors"
	"strconv"

	"retrochain/x/arcade/types"

	"cosmossdk.io/collections"
	errorsmod "cosmossdk.io/errors"
	"cosmossdk.io/math"
	sdk "github.com/cosmos/cosmos-sdk/types"
)

// RewardTokensPerThousandPoints defines how many uretro tokens are rewarded per 1000 points scored.
const RewardTokensPerThousandPoints = 1000

// EndSession handles ending a game session and distributing rewards.
// It validates the session ownership, marks it as completed, and rewards the player based on score.
func (k *msgServer) EndSession(ctx context.Context, sessionID uint64, player string) (*types.GameSession, error) {
	playerAddr, err := k.addressCodec.StringToBytes(player)
	if err != nil {
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

	// Get current block time
	sdkCtx := sdk.UnwrapSDKContext(ctx)
	endTime := sdkCtx.BlockTime().Unix()

	// Mark session as completed
	session.Status = types.SessionStatusCompleted
	session.EndTime = endTime

	// Store the updated session
	if err := k.SetSession(ctx, session); err != nil {
		return nil, errorsmod.Wrap(err, "failed to update session")
	}

	// Calculate and distribute rewards based on score
	// Reward: 1000 uretro per 1000 points (1:1 ratio per point)
	if session.CurrentScore > 0 {
		rewardAmount := (session.CurrentScore / 1000) * RewardTokensPerThousandPoints
		if rewardAmount > 0 {
			coins := sdk.NewCoins(sdk.NewCoin("uretro", math.NewIntFromUint64(rewardAmount)))
			if err := k.bankKeeper.SendCoinsFromModuleToAccount(ctx, types.ModuleName, playerAddr, coins); err != nil {
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
			sdk.NewAttribute(types.AttrGameID, session.GameID),
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
				sdk.NewAttribute(types.AttrGameID, session.GameID),
				sdk.NewAttribute(types.AttrPlayer, player),
				sdk.NewAttribute(types.AttrScore, strconv.FormatUint(session.CurrentScore, 10)),
			),
		)
	}

	return &session, nil
}

// GameOver handles ending a session when the player loses (game over).
func (k *msgServer) GameOver(ctx context.Context, sessionID uint64, player string) (*types.GameSession, error) {
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
	endTime := sdkCtx.BlockTime().Unix()

	// Mark session as game over
	session.Status = types.SessionStatusGameOver
	session.EndTime = endTime

	// Store the updated session
	if err := k.SetSession(ctx, session); err != nil {
		return nil, errorsmod.Wrap(err, "failed to update session")
	}

	// Emit game over event
	sdkCtx.EventManager().EmitEvent(
		sdk.NewEvent(
			types.EventGameOver,
			sdk.NewAttribute(types.AttrSessionID, strconv.FormatUint(sessionID, 10)),
			sdk.NewAttribute(types.AttrGameID, session.GameID),
			sdk.NewAttribute(types.AttrPlayer, player),
			sdk.NewAttribute(types.AttrScore, strconv.FormatUint(session.CurrentScore, 10)),
		),
	)

	return &session, nil
}
