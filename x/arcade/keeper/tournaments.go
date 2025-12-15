package keeper

import (
	"context"
	"errors"
	"sort"

	"cosmossdk.io/collections"
	sdk "github.com/cosmos/cosmos-sdk/types"

	"retrochain/x/arcade/types"
)

func (k Keeper) deductArcadeTokens(ctx context.Context, player string, amount uint64) error {
	if amount == 0 {
		return nil
	}
	entry, err := k.Leaderboard.Get(ctx, player)
	if err != nil {
		return types.ErrInsufficientFund
	}
	if entry.ArcadeTokens < amount {
		return types.ErrInsufficientFund
	}
	entry.ArcadeTokens -= amount
	return k.Leaderboard.Set(ctx, player, entry)
}

func (k Keeper) creditArcadeTokens(ctx context.Context, player string, amount uint64) error {
	if amount == 0 {
		return nil
	}
	return k.updateLeaderboard(ctx, player, 0, 0, 0, 0, amount)
}

// ProcessTournaments updates tournament status based on block time and finalizes completed tournaments.
func (k Keeper) ProcessTournaments(ctx context.Context) error {
	sdkCtx := sdk.UnwrapSDKContext(ctx)
	now := sdkCtx.BlockTime()

	var toUpdate []types.Tournament
	err := k.Tournaments.Walk(ctx, nil, func(_ string, t types.Tournament) (bool, error) {
		changed := false
		switch t.Status {
		case types.TournamentStatus_TOURNAMENT_REGISTRATION:
			if t.StartTime != nil && !now.Before(*t.StartTime) {
				t.Status = types.TournamentStatus_TOURNAMENT_ACTIVE
				changed = true
			}
		case types.TournamentStatus_TOURNAMENT_ACTIVE:
			if t.EndTime != nil && !now.Before(*t.EndTime) {
				// Finalize: rank participants, set winner, award prize pool.
				sort.Slice(t.Participants, func(i, j int) bool {
					if t.Participants[i] == nil {
						return false
					}
					if t.Participants[j] == nil {
						return true
					}
					return t.Participants[i].BestScore > t.Participants[j].BestScore
				})

				for i := range t.Participants {
					if t.Participants[i] != nil {
						t.Participants[i].Rank = uint64(i + 1)
					}
				}

				winner := ""
				if len(t.Participants) > 0 && t.Participants[0] != nil {
					winner = t.Participants[0].Player
				}
				if winner != "" {
					t.Winner = winner
					if err := k.creditArcadeTokens(ctx, winner, t.PrizePool); err == nil {
						_ = k.updateLeaderboard(ctx, winner, 0, 0, 0, 1, 0)
					}
				}

				t.Status = types.TournamentStatus_TOURNAMENT_COMPLETED
				changed = true
			}
		}

		if changed {
			toUpdate = append(toUpdate, t)
		}
		return false, nil
	})
	if err != nil {
		return err
	}

	for _, t := range toUpdate {
		if err := k.Tournaments.Set(ctx, t.TournamentId, t); err != nil {
			return err
		}
	}
	return nil
}

func (k Keeper) isAlreadyClaimed(ctx context.Context, player, achievementID string) (bool, error) {
	_, err := k.Achievements.Get(ctx, achievementKey(player, achievementID))
	if err == nil {
		return true, nil
	}
	if errors.Is(err, collections.ErrNotFound) {
		return false, nil
	}
	return false, err
}
