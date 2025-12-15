package keeper

import (
	"context"
	"errors"
	"regexp"
	"time"

	"cosmossdk.io/collections"
	sdk "github.com/cosmos/cosmos-sdk/types"

	"retrochain/x/arcade/types"
)

var achievementIDRe = regexp.MustCompile(`^[a-z0-9]+(?:-[a-z0-9]+)*$`)

func achievementKey(player, achievementID string) string {
	return player + "/" + achievementID
}

type achievementDef struct {
	reward uint64
	check  func(ctx context.Context, k Keeper, player string, gameID string) (bool, error)
}

func (k Keeper) achievementDefs() map[string]achievementDef {
	// Rewards are in "arcade tokens" (tracked in leaderboard.ArcadeTokens).
	return map[string]achievementDef{
		"first-game": {
			reward: 10,
			check: func(ctx context.Context, k Keeper, player string, _ string) (bool, error) {
				sessions, err := k.ListPlayerSessions(ctx, player)
				if err != nil {
					return false, err
				}
				return len(sessions) >= 1, nil
			},
		},
		"first-win": {
			reward: 25,
			check: func(ctx context.Context, k Keeper, player string, _ string) (bool, error) {
				sessions, err := k.ListPlayerSessions(ctx, player)
				if err != nil {
					return false, err
				}
				for _, s := range sessions {
					if s.Status == types.SessionStatusCompleted {
						return true, nil
					}
				}
				return false, nil
			},
		},
		"coin-collector": {
			reward: 25,
			check: func(ctx context.Context, k Keeper, player string, _ string) (bool, error) {
				coins, err := k.PlayerCoinsInserted.Get(ctx, player)
				if err != nil {
					if errors.Is(err, collections.ErrNotFound) {
						return false, nil
					}
					return false, err
				}
				return coins >= 10, nil
			},
		},
		"quick-start": {
			reward: 25,
			check: func(ctx context.Context, k Keeper, player string, _ string) (bool, error) {
				achieved, err := k.PlayerQuickStartAchieved.Get(ctx, player)
				if err != nil {
					if errors.Is(err, collections.ErrNotFound) {
						return false, nil
					}
					return false, err
				}
				return achieved, nil
			},
		},
		"multi-genre-master": {
			reward: 75,
			check: func(ctx context.Context, k Keeper, player string, _ string) (bool, error) {
				sessions, err := k.ListPlayerSessions(ctx, player)
				if err != nil {
					return false, err
				}
				genres := map[types.GameGenre]struct{}{}
				for _, s := range sessions {
					g, err := k.GetArcadeGame(ctx, s.GameId)
					if err == nil && g != nil {
						genres[g.Genre] = struct{}{}
					}
				}
				return len(genres) >= 5, nil
			},
		},
		"high-scorer": {
			reward: 50,
			check: func(ctx context.Context, k Keeper, player string, _ string) (bool, error) {
				found := false
				err := k.HighScores.Walk(ctx, nil, func(_ uint64, hs types.HighScore) (bool, error) {
					if hs.Player == player {
						found = true
						return true, nil
					}
					return false, nil
				})
				if err != nil {
					return false, err
				}
				return found, nil
			},
		},
		"tournament-player": {
			reward: 50,
			check: func(ctx context.Context, k Keeper, player string, _ string) (bool, error) {
				found := false
				err := k.Tournaments.Walk(ctx, nil, func(_ string, t types.Tournament) (bool, error) {
					for _, p := range t.Participants {
						if p != nil && p.Player == player {
							found = true
							return true, nil
						}
					}
					return false, nil
				})
				if err != nil {
					return false, err
				}
				return found, nil
			},
		},
		"power-user": {
			reward: 150,
			check: func(ctx context.Context, k Keeper, player string, _ string) (bool, error) {
				sessions, err := k.ListPlayerSessions(ctx, player)
				if err != nil {
					return false, err
				}
				var used uint64
				for _, s := range sessions {
					used += uint64(len(s.PowerUpsCollected))
				}
				return used >= 50, nil
			},
		},
		"comeback-kid": {
			reward: 150,
			check: func(ctx context.Context, k Keeper, player string, _ string) (bool, error) {
				sessions, err := k.ListPlayerSessions(ctx, player)
				if err != nil {
					return false, err
				}
				var continues uint64
				for _, s := range sessions {
					continues += s.ContinuesUsed
				}
				return continues >= 10, nil
			},
		},
		"high-roller": {
			reward: 150,
			check: func(ctx context.Context, k Keeper, player string, _ string) (bool, error) {
				sessions, err := k.ListPlayerSessions(ctx, player)
				if err != nil {
					return false, err
				}
				var spent uint64
				for _, s := range sessions {
					spent += s.CreditsUsed
				}
				return spent >= 100, nil
			},
		},
		"arcade-legend": {
			reward: 250,
			check: func(ctx context.Context, k Keeper, player string, _ string) (bool, error) {
				entries, err := k.getLeaderboard(ctx)
				if err != nil {
					return false, err
				}
				for _, e := range entries {
					if e.Player == player {
						return e.Rank > 0 && e.Rank <= 10, nil
					}
				}
				return false, nil
			},
		},
		"top-of-the-world": {
			reward: 500,
			check: func(ctx context.Context, k Keeper, player string, _ string) (bool, error) {
				entries, err := k.getLeaderboard(ctx)
				if err != nil {
					return false, err
				}
				for _, e := range entries {
					if e.Player == player {
						return e.Rank == 1, nil
					}
				}
				return false, nil
			},
		},
		"tournament-champion": {
			reward: 300,
			check: func(ctx context.Context, k Keeper, player string, _ string) (bool, error) {
				e, err := k.Leaderboard.Get(ctx, player)
				if err != nil {
					if errors.Is(err, collections.ErrNotFound) {
						return false, nil
					}
					return false, err
				}
				return e.TournamentsWon >= 1, nil
			},
		},
		"ultimate-champion": {
			reward: 500,
			check: func(ctx context.Context, k Keeper, player string, _ string) (bool, error) {
				e, err := k.Leaderboard.Get(ctx, player)
				if err != nil {
					if errors.Is(err, collections.ErrNotFound) {
						return false, nil
					}
					return false, err
				}
				return e.TournamentsWon >= 10, nil
			},
		},
		"arcade-mogul": {
			reward: 500,
			check: func(ctx context.Context, k Keeper, player string, _ string) (bool, error) {
				e, err := k.Leaderboard.Get(ctx, player)
				if err != nil {
					if errors.Is(err, collections.ErrNotFound) {
						return false, nil
					}
					return false, err
				}
				return e.ArcadeTokens >= 1_000_000, nil
			},
		},
		"legendary-player": {
			reward: 500,
			check: func(ctx context.Context, k Keeper, player string, _ string) (bool, error) {
				sessions, err := k.ListPlayerSessions(ctx, player)
				if err != nil {
					return false, err
				}
				return len(sessions) >= 1000, nil
			},
		},
	}
}

func (k Keeper) canClaimAchievement(ctx context.Context, player, achievementID, gameID string) (reward uint64, ok bool, err error) {
	if achievementID == "" || !achievementIDRe.MatchString(achievementID) {
		return 0, false, nil
	}
	defs := k.achievementDefs()
	def, exists := defs[achievementID]
	if !exists {
		return 0, false, nil
	}

	eligible, err := def.check(ctx, k, player, gameID)
	if err != nil {
		return 0, false, err
	}
	if !eligible {
		return 0, false, nil
	}

	params, err := k.getParams(ctx)
	if err != nil {
		return 0, false, err
	}
	mult := uint64(params.AchievementRewardMultiplier)
	if mult == 0 {
		mult = 1
	}
	return def.reward * mult, true, nil
}

func (k Keeper) detectNewlyUnlockedAchievements(ctx context.Context, player, gameID string) ([]string, error) {
	defs := k.achievementDefs()
	unlocked := make([]string, 0, len(defs))
	for id, def := range defs {
		// Skip if already claimed.
		if _, err := k.Achievements.Get(ctx, achievementKey(player, id)); err == nil {
			continue
		}
		eligible, err := def.check(ctx, k, player, gameID)
		if err != nil {
			return nil, err
		}
		if eligible {
			unlocked = append(unlocked, id)
		}
	}
	return unlocked, nil
}

func (k Keeper) recordCoinInsert(ctx context.Context, player string, credits uint64) error {
	current, err := k.PlayerCoinsInserted.Get(ctx, player)
	if err != nil {
		if !errors.Is(err, collections.ErrNotFound) {
			return err
		}
		current = 0
	}
	if err := k.PlayerCoinsInserted.Set(ctx, player, current+credits); err != nil {
		return err
	}

	sdkCtx := sdk.UnwrapSDKContext(ctx)
	return k.PlayerLastCoinInsertTime.Set(ctx, player, sdkCtx.BlockTime().Unix())
}

func (k Keeper) maybeRecordQuickStart(ctx context.Context, player string, start time.Time) error {
	if achieved, err := k.PlayerQuickStartAchieved.Get(ctx, player); err == nil && achieved {
		return nil
	}
	last, err := k.PlayerLastCoinInsertTime.Get(ctx, player)
	if err != nil {
		if errors.Is(err, collections.ErrNotFound) {
			return nil
		}
		return err
	}
	if start.Unix()-last <= 60 {
		return k.PlayerQuickStartAchieved.Set(ctx, player, true)
	}
	return nil
}
