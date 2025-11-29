package keeper

import (
	"context"
	"errors"
	"sort"

	"cosmossdk.io/collections"

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
func (k Keeper) GetHighScores(ctx context.Context, gameID string, limit int) ([]types.GameSession, error) {
	var sessions []types.GameSession

	err := k.GameSessions.Walk(ctx, nil, func(sessionID uint64, data []byte) (bool, error) {
		session, err := k.GetSession(ctx, sessionID)
		if err != nil {
			return true, err
		}
		if session.GameID == gameID && session.Status == types.SessionStatusCompleted {
			sessions = append(sessions, session)
		}
		return false, nil
	})

	if err != nil {
		return nil, err
	}

	// Sort by score (descending) using sort.Slice for O(n log n) complexity
	sort.Slice(sessions, func(i, j int) bool {
		return sessions[i].CurrentScore > sessions[j].CurrentScore
	})

	// Limit results
	if limit > 0 && len(sessions) > limit {
		sessions = sessions[:limit]
	}

	return sessions, nil
}
