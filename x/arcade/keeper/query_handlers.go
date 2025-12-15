package keeper

import (
	"context"

	query "github.com/cosmos/cosmos-sdk/types/query"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"retrochain/x/arcade/types"
)

func (q *queryServer) ListGames(ctx context.Context, req *types.QueryListGamesRequest) (*types.QueryListGamesResponse, error) {
	if req == nil {
		return nil, status.Error(codes.InvalidArgument, "invalid request")
	}
	games, err := q.k.ListArcadeGames(ctx, req.Genre, req.ActiveOnly)
	if err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}

	paginated, pageResp := paginateArcade(games, req.Pagination)
	return &types.QueryListGamesResponse{Games: paginated, Pagination: pageResp}, nil
}

func (q *queryServer) GetGame(ctx context.Context, req *types.QueryGetGameRequest) (*types.QueryGetGameResponse, error) {
	if req == nil || req.GameId == "" {
		return nil, status.Error(codes.InvalidArgument, "game_id required")
	}
	game, err := q.k.GetArcadeGame(ctx, req.GameId)
	if err != nil {
		return nil, status.Error(codes.NotFound, err.Error())
	}
	return &types.QueryGetGameResponse{Game: *game}, nil
}

func (q *queryServer) GetSession(ctx context.Context, req *types.QueryGetSessionRequest) (*types.QueryGetSessionResponse, error) {
	if req == nil || req.SessionId == 0 {
		return nil, status.Error(codes.InvalidArgument, "session_id required")
	}
	session, err := q.k.GetSessionQuery(ctx, req.SessionId)
	if err != nil {
		return nil, status.Error(codes.NotFound, err.Error())
	}
	return &types.QueryGetSessionResponse{Session: *session}, nil
}

func (q *queryServer) ListPlayerSessions(ctx context.Context, req *types.QueryListPlayerSessionsRequest) (*types.QueryListPlayerSessionsResponse, error) {
	if req == nil || req.Player == "" {
		return nil, status.Error(codes.InvalidArgument, "player required")
	}
	sessions, err := q.k.ListPlayerSessions(ctx, req.Player)
	if err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}

	// Optional status filtering
	if req.Status != types.SessionStatus_STATUS_UNSPECIFIED {
		filtered := make([]types.GameSession, 0, len(sessions))
		for _, s := range sessions {
			if s.Status == req.Status {
				filtered = append(filtered, s)
			}
		}
		sessions = filtered
	}

	paginated, pageResp := paginateSessions(sessions, req.Pagination)
	return &types.QueryListPlayerSessionsResponse{Sessions: paginated, Pagination: pageResp}, nil
}

func (q *queryServer) GetHighScores(ctx context.Context, req *types.QueryGetHighScoresRequest) (*types.QueryGetHighScoresResponse, error) {
	if req == nil || req.GameId == "" {
		return nil, status.Error(codes.InvalidArgument, "game_id required")
	}
	limit := int(req.Limit)
	if limit <= 0 {
		limit = 10
	}
	scores, err := q.k.GetHighScores(ctx, req.GameId, limit)
	if err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}
	return &types.QueryGetHighScoresResponse{Scores: scores}, nil
}

func (q *queryServer) GetLeaderboard(ctx context.Context, req *types.QueryGetLeaderboardRequest) (*types.QueryGetLeaderboardResponse, error) {
	if req == nil {
		return nil, status.Error(codes.InvalidArgument, "invalid request")
	}
	entries, err := q.k.getLeaderboard(ctx)
	if err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}
	paginated, pageResp := paginateLeaderboard(entries, req.Pagination)
	return &types.QueryGetLeaderboardResponse{Entries: paginated, Pagination: pageResp}, nil
}

func (q *queryServer) GetPlayerStats(ctx context.Context, req *types.QueryGetPlayerStatsRequest) (*types.QueryGetPlayerStatsResponse, error) {
	if req == nil || req.Player == "" {
		return nil, status.Error(codes.InvalidArgument, "player required")
	}
	stats := types.LeaderboardEntry{Player: req.Player}
	// Prefer the ranked view for rank/title consistency.
	if entries, err := q.k.getLeaderboard(ctx); err == nil {
		for _, e := range entries {
			if e.Player == req.Player {
				stats = e
				break
			}
		}
	} else if entry, err2 := q.k.Leaderboard.Get(ctx, req.Player); err2 == nil {
		stats = entry
	}

	sessions, err := q.k.ListPlayerSessions(ctx, req.Player)
	if err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}

	var creditsSpent uint64
	var activeSessions uint64
	gameCounts := map[string]uint64{}
	for _, s := range sessions {
		creditsSpent += s.CreditsUsed
		if s.Status == types.SessionStatusActive {
			activeSessions++
		}
		gameCounts[s.GameId]++
	}

	// Determine favorite games by highest count
	var favoriteGames []string
	var maxCount uint64
	for gameID, count := range gameCounts {
		if count > maxCount {
			favoriteGames = []string{gameID}
			maxCount = count
		} else if count == maxCount {
			favoriteGames = append(favoriteGames, gameID)
		}
	}

	return &types.QueryGetPlayerStatsResponse{
		Stats:             stats,
		TotalCreditsSpent: creditsSpent,
		ActiveSessions:    activeSessions,
		FavoriteGames:     favoriteGames,
	}, nil
}

func (q *queryServer) ListAchievements(ctx context.Context, req *types.QueryListAchievementsRequest) (*types.QueryListAchievementsResponse, error) {
	if req == nil || req.Player == "" {
		return nil, status.Error(codes.InvalidArgument, "player required")
	}
	var achievements []types.PlayerAchievement
	err := q.k.Achievements.Walk(ctx, nil, func(_ string, ach types.PlayerAchievement) (bool, error) {
		if ach.Player == req.Player {
			achievements = append(achievements, ach)
		}
		return false, nil
	})
	if err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}

	paginated, pageResp := paginateAchievements(achievements, req.Pagination)
	return &types.QueryListAchievementsResponse{Achievements: paginated, Pagination: pageResp}, nil
}

func (q *queryServer) ListTournaments(ctx context.Context, req *types.QueryListTournamentsRequest) (*types.QueryListTournamentsResponse, error) {
	if req == nil {
		return nil, status.Error(codes.InvalidArgument, "invalid request")
	}
	var tournaments []types.Tournament
	err := q.k.Tournaments.Walk(ctx, nil, func(_ string, t types.Tournament) (bool, error) {
		if req.Status != types.TournamentStatus_TOURNAMENT_UNSPECIFIED && t.Status != req.Status {
			return false, nil
		}
		tournaments = append(tournaments, t)
		return false, nil
	})
	if err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}
	if req.Pagination != nil && req.Pagination.Limit > 0 && req.Pagination.Limit < uint64(len(tournaments)) {
		start := int(req.Pagination.Offset)
		if start > len(tournaments) {
			start = len(tournaments)
		}
		end := start + int(req.Pagination.Limit)
		if end > len(tournaments) {
			end = len(tournaments)
		}
		return &types.QueryListTournamentsResponse{
			Tournaments: tournaments[start:end],
			Pagination:  &query.PageResponse{Total: uint64(len(tournaments))},
		}, nil
	}
	return &types.QueryListTournamentsResponse{Tournaments: tournaments, Pagination: &query.PageResponse{Total: uint64(len(tournaments))}}, nil
}

func (q *queryServer) GetTournament(ctx context.Context, req *types.QueryGetTournamentRequest) (*types.QueryGetTournamentResponse, error) {
	if req == nil || req.TournamentId == "" {
		return nil, status.Error(codes.InvalidArgument, "tournament_id required")
	}
	tour, err := q.k.Tournaments.Get(ctx, req.TournamentId)
	if err != nil {
		return nil, status.Error(codes.NotFound, err.Error())
	}
	return &types.QueryGetTournamentResponse{Tournament: tour}, nil
}

func (q *queryServer) GetPlayerCredits(ctx context.Context, req *types.QueryGetPlayerCreditsRequest) (*types.QueryGetPlayerCreditsResponse, error) {
	if req == nil || req.Player == "" {
		return nil, status.Error(codes.InvalidArgument, "player required")
	}
	credits, err := q.k.GetPlayerCreditsQuery(ctx, req.Player)
	if err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}
	arcadeTokens := uint64(0)
	if entry, err := q.k.Leaderboard.Get(ctx, req.Player); err == nil {
		arcadeTokens = entry.ArcadeTokens
	}
	return &types.QueryGetPlayerCreditsResponse{Credits: credits, ArcadeTokens: arcadeTokens}, nil
}

// Pagination helpers (offset-based for small collections)
func paginateArcade(items []types.ArcadeGame, page *query.PageRequest) ([]types.ArcadeGame, *query.PageResponse) {
	if page == nil || page.Limit == 0 {
		return items, &query.PageResponse{Total: uint64(len(items))}
	}
	start := int(page.Offset)
	if start > len(items) {
		start = len(items)
	}
	end := start + int(page.Limit)
	if end > len(items) {
		end = len(items)
	}
	return items[start:end], &query.PageResponse{Total: uint64(len(items))}
}

func paginateSessions(items []types.GameSession, page *query.PageRequest) ([]types.GameSession, *query.PageResponse) {
	if page == nil || page.Limit == 0 {
		return items, &query.PageResponse{Total: uint64(len(items))}
	}
	start := int(page.Offset)
	if start > len(items) {
		start = len(items)
	}
	end := start + int(page.Limit)
	if end > len(items) {
		end = len(items)
	}
	return items[start:end], &query.PageResponse{Total: uint64(len(items))}
}

func paginateLeaderboard(items []types.LeaderboardEntry, page *query.PageRequest) ([]types.LeaderboardEntry, *query.PageResponse) {
	if page == nil || page.Limit == 0 {
		return items, &query.PageResponse{Total: uint64(len(items))}
	}
	start := int(page.Offset)
	if start > len(items) {
		start = len(items)
	}
	end := start + int(page.Limit)
	if end > len(items) {
		end = len(items)
	}
	return items[start:end], &query.PageResponse{Total: uint64(len(items))}
}

func paginateAchievements(items []types.PlayerAchievement, page *query.PageRequest) ([]types.PlayerAchievement, *query.PageResponse) {
	if page == nil || page.Limit == 0 {
		return items, &query.PageResponse{Total: uint64(len(items))}
	}
	start := int(page.Offset)
	if start > len(items) {
		start = len(items)
	}
	end := start + int(page.Limit)
	if end > len(items) {
		end = len(items)
	}
	return items[start:end], &query.PageResponse{Total: uint64(len(items))}
}
