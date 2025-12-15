package keeper

import (
	"context"
	"encoding/json"
	"errors"

	"cosmossdk.io/collections"

	"retrochain/x/arcade/types"
)

// InitGenesis sets module params from genesis.
func (k Keeper) InitGenesis(ctx context.Context, genState types.GenesisState) error {
	if err := genState.Params.Validate(); err != nil {
		return err
	}

	if err := k.Params.Set(ctx, genState.Params); err != nil {
		return err
	}

	// Restore registered games
	for _, game := range genState.Games {
		if err := k.ArcadeGames.Set(ctx, game.GameId, game); err != nil {
			return err
		}
	}

	// Restore sessions
	var maxSessionID uint64
	for _, session := range genState.Sessions {
		if err := k.SetSession(ctx, session); err != nil {
			return err
		}
		if session.SessionId > maxSessionID {
			maxSessionID = session.SessionId
		}
	}

	// Restore high scores
	var maxHighScoreID uint64
	for i, hs := range genState.HighScores {
		id := uint64(i + 1)
		if err := k.HighScores.Set(ctx, id, hs); err != nil {
			return err
		}
		maxHighScoreID = id
	}

	// Restore leaderboard entries
	for _, entry := range genState.Leaderboard {
		if err := k.Leaderboard.Set(ctx, entry.Player, entry); err != nil {
			return err
		}
	}

	// Restore achievements keyed by player/id
	for _, ach := range genState.Achievements {
		key := ach.Player + "/" + ach.AchievementId
		if err := k.Achievements.Set(ctx, key, ach); err != nil {
			return err
		}
	}

	// Restore tournaments
	for _, tour := range genState.Tournaments {
		if err := k.Tournaments.Set(ctx, tour.TournamentId, tour); err != nil {
			return err
		}
	}

	// Restore counters
	if genState.NextSessionId > 0 {
		if err := k.SessionCounter.Set(ctx, genState.NextSessionId); err != nil {
			return err
		}
	} else if maxSessionID > 0 {
		if err := k.SessionCounter.Set(ctx, maxSessionID+1); err != nil {
			return err
		}
	}
	if maxHighScoreID > 0 {
		if err := k.HighScoreCounter.Set(ctx, maxHighScoreID); err != nil {
			return err
		}
	}

	return nil
}

// ExportGenesis returns the current module params for genesis export.
func (k Keeper) ExportGenesis(ctx context.Context) (*types.GenesisState, error) {
	params, err := k.Params.Get(ctx)
	if err != nil {
		if !errors.Is(err, collections.ErrNotFound) {
			return nil, err
		}
		params = types.DefaultParams()
	}

	state := types.GenesisState{Params: params}

	// Export games
	err = k.ArcadeGames.Walk(ctx, nil, func(_ string, game types.ArcadeGame) (bool, error) {
		state.Games = append(state.Games, game)
		return false, nil
	})
	if err != nil {
		return nil, err
	}

	// Export sessions
	err = k.GameSessions.Walk(ctx, nil, func(id uint64, data []byte) (bool, error) {
		var session types.GameSession
		if err := json.Unmarshal(data, &session); err != nil {
			return true, err
		}
		state.Sessions = append(state.Sessions, session)
		if id > state.NextSessionId {
			state.NextSessionId = id + 1
		}
		return false, nil
	})
	if err != nil {
		return nil, err
	}

	// Export high scores
	err = k.HighScores.Walk(ctx, nil, func(id uint64, hs types.HighScore) (bool, error) {
		state.HighScores = append(state.HighScores, hs)
		return false, nil
	})
	if err != nil {
		return nil, err
	}

	// Export leaderboard
	err = k.Leaderboard.Walk(ctx, nil, func(_ string, entry types.LeaderboardEntry) (bool, error) {
		state.Leaderboard = append(state.Leaderboard, entry)
		return false, nil
	})
	if err != nil {
		return nil, err
	}

	// Export achievements
	err = k.Achievements.Walk(ctx, nil, func(_ string, ach types.PlayerAchievement) (bool, error) {
		state.Achievements = append(state.Achievements, ach)
		return false, nil
	})
	if err != nil {
		return nil, err
	}

	// Export tournaments
	err = k.Tournaments.Walk(ctx, nil, func(_ string, tour types.Tournament) (bool, error) {
		state.Tournaments = append(state.Tournaments, tour)
		return false, nil
	})
	if err != nil {
		return nil, err
	}

	return &state, nil
}
