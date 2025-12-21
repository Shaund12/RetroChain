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

	params, err := k.getParams(ctx)
	if err != nil {
		return nil, errorsmod.Wrap(err, "failed to load params")
	}

	priorScore := session.CurrentScore
	// Update session fields
	session.CurrentScore = msg.Score
	if msg.Level > 0 {
		session.Level = msg.Level
	}

	// Calculate score delta for leaderboard updates
	var delta uint64
	if msg.Score > priorScore {
		delta = msg.Score - priorScore
	}

	// Persist session update (endSessionInternal will overwrite on game_over)
	if err := k.SetSession(ctx, session); err != nil {
		return nil, errorsmod.Wrap(err, "failed to update session")
	}

	if delta > 0 {
		if err := k.updateLeaderboard(ctx, msg.Creator, delta, 0, 0, 0, 0); err != nil {
			return nil, errorsmod.Wrap(err, "failed to update leaderboard")
		}
	}

	sdkCtx := sdk.UnwrapSDKContext(ctx)
	sdkCtx.EventManager().EmitEvent(
		sdk.NewEvent(
			types.EventScoreUpdated,
			sdk.NewAttribute(types.AttrSessionID, strconv.FormatUint(msg.SessionId, 10)),
			sdk.NewAttribute(types.AttrPlayer, msg.Creator),
			sdk.NewAttribute(types.AttrScore, strconv.FormatUint(msg.Score, 10)),
		),
	)

	isHighScore := false
	rank := uint64(0)
	var earnedTokens uint64

	// If game_over, finalize the session (awards score-based tokens on completion).
	if msg.GameOver {
		if _, err := k.endSessionInternal(ctx, msg.SessionId, msg.Creator, msg.Score, msg.Level); err != nil {
			return nil, err
		}
		// Score completion reward (arcade tokens)
		base := msg.Score / 1000
		mult := uint64(params.TokensPerThousandPoints)
		if mult > 0 && base > (^uint64(0))/mult {
			return nil, errorsmod.Wrap(types.ErrInvalidRequest, "reward calculation overflow")
		}
		earnedTokens = base * mult
	} else if delta > 0 {
		// Incremental score reward (arcade tokens)
		base := delta / 1000
		mult := uint64(params.TokensPerThousandPoints)
		if mult > 0 && base > (^uint64(0))/mult {
			return nil, errorsmod.Wrap(types.ErrInvalidRequest, "reward calculation overflow")
		}
		earnedTokens = base * mult
		if earnedTokens > 0 {
			if err := k.updateLeaderboard(ctx, msg.Creator, 0, 0, 0, 0, earnedTokens); err != nil {
				return nil, errorsmod.Wrap(err, "failed to credit leaderboard tokens")
			}
		}
	}

	// Track/compute high-score status and apply bonus.
	if msg.GameOver {
		if hs, err := k.upsertHighScore(ctx, session.GameId, session.Player, msg.Score, session.Level, sdkCtx.BlockTime()); err == nil {
			isHighScore = hs != nil && hs.Score == msg.Score
		}
	}
	if isHighScore {
		scores, err := k.GetHighScores(ctx, session.GameId, 0)
		if err == nil {
			for _, sc := range scores {
				if sc.Player == session.Player && sc.Score == msg.Score {
					rank = sc.Rank
					break
				}
			}
		}
		if params.HighScoreReward > 0 {
			bonus := uint64(params.HighScoreReward)
			if err := k.updateLeaderboard(ctx, msg.Creator, 0, 0, 0, 0, bonus); err == nil {
				earnedTokens += bonus
			}
		}
	}

	achievementsUnlocked, err := k.detectNewlyUnlockedAchievements(ctx, msg.Creator, session.GameId)
	if err != nil {
		return nil, errorsmod.Wrap(err, "failed to evaluate achievements")
	}

	return &types.MsgSubmitScoreResponse{IsHighScore: isHighScore, Rank: rank, TokensEarned: earnedTokens, AchievementsUnlocked: achievementsUnlocked}, nil
}
