package keeper

import (
	"context"
	"errors"
	"sort"
	"time"

	"cosmossdk.io/collections"
	errorsmod "cosmossdk.io/errors"

	"retrochain/x/arcade/types"
)

// GetPlayerCreditsQuery returns the credits for a specific player address.
// This is a helper method that can be used by CLI or REST queries.
func (k Keeper) GetPlayerCreditsQuery(ctx context.Context, player string) (uint64, error) {
	credits, err := k.PlayerCredits.Get(ctx, player)
	if err != nil {
		if errors.Is(err, collections.ErrNotFound) {
			return 0, nil
		}
		return 0, err
	}
	return credits, nil
}

// GetSessionQuery returns a game session by its ID.
// This is a helper method that can be used by CLI or REST queries.
func (k Keeper) GetSessionQuery(ctx context.Context, sessionID uint64) (*types.GameSession, error) {
	session, err := k.GetSession(ctx, sessionID)
	if err != nil {
		if errors.Is(err, collections.ErrNotFound) {
			return nil, types.ErrNotFound
		}
		return nil, err
	}
	return &session, nil
}

// ListPlayerSessions returns all sessions for a specific player.
// This iterates through all sessions and filters by player address.
func (k Keeper) ListPlayerSessions(ctx context.Context, player string) ([]types.GameSession, error) {
	var sessions []types.GameSession

	// Iterate through all game sessions
	err := k.GameSessions.Walk(ctx, nil, func(sessionID uint64, data []byte) (bool, error) {
		session, err := k.GetSession(ctx, sessionID)
		if err != nil {
			return true, err // stop on error
		}
		if session.Player == player {
			sessions = append(sessions, session)
		}
		return false, nil // continue
	})

	if err != nil {
		return nil, err
	}

	return sessions, nil
}

// ListArcadeGames returns registered games, optionally filtered by genre/active flag.
func (k Keeper) ListArcadeGames(ctx context.Context, genre types.GameGenre, activeOnly bool) ([]types.ArcadeGame, error) {
	var games []types.ArcadeGame

	err := k.ArcadeGames.Walk(ctx, nil, func(_ string, game types.ArcadeGame) (bool, error) {
		if activeOnly && !game.Active {
			return false, nil
		}
		if genre != types.GameGenre_GENRE_UNSPECIFIED && game.Genre != genre {
			return false, nil
		}
		games = append(games, game)
		return false, nil
	})

	if err != nil {
		return nil, err
	}

	return games, nil
}

// GetArcadeGame fetches a single game by id.
func (k Keeper) GetArcadeGame(ctx context.Context, gameID string) (*types.ArcadeGame, error) {
	game, err := k.ArcadeGames.Get(ctx, gameID)
	if err != nil {
		if errors.Is(err, collections.ErrNotFound) {
			return nil, types.ErrNotFound
		}
		return nil, err
	}
	return &game, nil
}

// ListActiveSessions returns all active game sessions.
func (k Keeper) ListActiveSessions(ctx context.Context) ([]types.GameSession, error) {
	var sessions []types.GameSession

	err := k.GameSessions.Walk(ctx, nil, func(sessionID uint64, data []byte) (bool, error) {
		session, err := k.GetSession(ctx, sessionID)
		if err != nil {
			return true, err
		}
		if session.Status == types.SessionStatusActive {
			sessions = append(sessions, session)
		}
		return false, nil
	})

	if err != nil {
		return nil, err
	}

	return sessions, nil
}

// GetHighScores returns sessions sorted by score for a specific game.
// This is a basic implementation - for production, consider using an index.
func (k Keeper) GetHighScores(ctx context.Context, gameID string, limit int) ([]types.HighScore, error) {
	var scores []types.HighScore

	err := k.HighScores.Walk(ctx, nil, func(id uint64, hs types.HighScore) (bool, error) {
		if hs.GameId == gameID {
			scores = append(scores, hs)
		}
		return false, nil
	})
	if err != nil {
		return nil, err
	}

	// Sort by score descending, then timestamp
	sort.Slice(scores, func(i, j int) bool {
		if scores[i].Score == scores[j].Score {
			if scores[i].Timestamp == nil || scores[j].Timestamp == nil {
				return scores[j].Timestamp == nil
			}
			return scores[i].Timestamp.Before(*scores[j].Timestamp)
		}
		return scores[i].Score > scores[j].Score
	})

	if limit > 0 && len(scores) > limit {
		scores = scores[:limit]
	}

	for i := range scores {
		rank := uint64(i + 1)
		scores[i].Rank = rank
		if scores[i].Timestamp == nil {
			now := time.Now().UTC()
			scores[i].Timestamp = &now
		}
	}

	return scores, nil
}

// upsertHighScore records a high score for the given game/player if it improves their best score.
func (k Keeper) upsertHighScore(ctx context.Context, gameID, player string, score, level uint64, ts time.Time) (*types.HighScore, error) {
	var existingID *uint64
	var existing types.HighScore

	err := k.HighScores.Walk(ctx, nil, func(id uint64, hs types.HighScore) (bool, error) {
		if hs.GameId == gameID && hs.Player == player {
			existingID = &id
			existing = hs
			return true, nil
		}
		return false, nil
	})
	if err != nil {
		return nil, err
	}

	if existingID != nil && existing.Score >= score {
		// No improvement; return existing record
		existing.Rank = 0
		return &existing, nil
	}

	// Build the new/updated record
	record := types.HighScore{
		GameId:       gameID,
		Player:       player,
		Score:        score,
		LevelReached: level,
		Timestamp:    &ts,
	}

	if existingID != nil {
		if err := k.HighScores.Set(ctx, *existingID, record); err != nil {
			return nil, err
		}
		return &record, nil
	}

	id, err := k.HighScoreCounter.Next(ctx)
	if err != nil {
		return nil, err
	}
	if err := k.HighScores.Set(ctx, id, record); err != nil {
		return nil, err
	}
	return &record, nil
}

// updateLeaderboard aggregates player totals.
func (k Keeper) updateLeaderboard(ctx context.Context, player string, scoreDelta, gamesDelta uint64, achievementsDelta uint64, tournamentsWonDelta uint64, tokensDelta uint64) error {
	entry, err := k.Leaderboard.Get(ctx, player)
	if err != nil {
		if !errors.Is(err, collections.ErrNotFound) {
			return err
		}
		entry = types.LeaderboardEntry{Player: player}
	}

	max := ^uint64(0)
	if scoreDelta > 0 && entry.TotalScore > max-scoreDelta {
		return errorsmod.Wrap(types.ErrInvalidRequest, "total_score overflow")
	}
	if gamesDelta > 0 && entry.GamesPlayed > max-gamesDelta {
		return errorsmod.Wrap(types.ErrInvalidRequest, "games_played overflow")
	}
	if achievementsDelta > 0 && entry.AchievementsUnlocked > max-achievementsDelta {
		return errorsmod.Wrap(types.ErrInvalidRequest, "achievements_unlocked overflow")
	}
	if tournamentsWonDelta > 0 && entry.TournamentsWon > max-tournamentsWonDelta {
		return errorsmod.Wrap(types.ErrInvalidRequest, "tournaments_won overflow")
	}
	if tokensDelta > 0 && entry.ArcadeTokens > max-tokensDelta {
		return errorsmod.Wrap(types.ErrInvalidRequest, "arcade_tokens overflow")
	}

	entry.TotalScore += scoreDelta
	entry.GamesPlayed += gamesDelta
	entry.AchievementsUnlocked += achievementsDelta
	entry.TournamentsWon += tournamentsWonDelta
	entry.ArcadeTokens += tokensDelta

	return k.Leaderboard.Set(ctx, player, entry)
}

// getLeaderboard builds a ranked leaderboard view.
func (k Keeper) getLeaderboard(ctx context.Context) ([]types.LeaderboardEntry, error) {
	var entries []types.LeaderboardEntry

	err := k.Leaderboard.Walk(ctx, nil, func(_ string, entry types.LeaderboardEntry) (bool, error) {
		entries = append(entries, entry)
		return false, nil
	})
	if err != nil {
		return nil, err
	}

	sort.Slice(entries, func(i, j int) bool {
		if entries[i].TotalScore == entries[j].TotalScore {
			return entries[i].GamesPlayed < entries[j].GamesPlayed
		}
		return entries[i].TotalScore > entries[j].TotalScore
	})

	for i := range entries {
		entries[i].Rank = uint64(i + 1)
		switch {
		case entries[i].Rank == 1:
			entries[i].Title = "Arcade Champion"
		case entries[i].Rank <= 10:
			entries[i].Title = "Arcade Legend"
		case entries[i].Rank <= 100:
			entries[i].Title = "Arcade Master"
		default:
			entries[i].Title = "Player"
		}
	}

	return entries, nil
}
