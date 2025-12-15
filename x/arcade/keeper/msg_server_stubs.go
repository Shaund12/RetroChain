package keeper

import (
	"context"
	"errors"
	"regexp"
	"sort"
	"strconv"
	"strings"

	"cosmossdk.io/collections"
	sdk "github.com/cosmos/cosmos-sdk/types"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"retrochain/x/arcade/types"
)

var initialsRe = regexp.MustCompile(`^[A-Z]{3}$`)

// EndSession processes MsgEndSession by delegating to the internal endSession logic.
func (k *msgServer) EndSession(ctx context.Context, msg *types.MsgEndSession) (*types.MsgEndSessionResponse, error) {
	if msg == nil {
		return nil, status.Error(codes.InvalidArgument, "invalid request")
	}
	session, err := k.endSessionInternal(ctx, msg.SessionId, msg.Creator, msg.FinalScore, msg.FinalLevel)
	if err != nil {
		return nil, err
	}
	summary := "session ended"
	if session != nil {
		summary = "session ended with score " + strconv.FormatUint(session.CurrentScore, 10)
	}
	return &types.MsgEndSessionResponse{SessionEnded: true, Summary: summary}, nil
}

// RegisterGame is currently unimplemented.
func (k *msgServer) RegisterGame(ctx context.Context, msg *types.MsgRegisterGame) (*types.MsgRegisterGameResponse, error) {
	if msg == nil {
		return nil, status.Error(codes.InvalidArgument, "invalid request")
	}
	if msg.Game.GameId == "" {
		return nil, status.Error(codes.InvalidArgument, "game_id required")
	}
	if _, err := k.addressCodec.StringToBytes(msg.Creator); err != nil {
		return nil, status.Error(codes.InvalidArgument, "invalid creator")
	}

	if _, err := k.ArcadeGames.Get(ctx, msg.Game.GameId); err == nil {
		return nil, status.Error(codes.AlreadyExists, "game already registered")
	}

	params, err := k.getParams(ctx)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to load params: %v", err)
	}

	// Normalize and validate difficulty bounds and credits per play
	if msg.Game.BaseDifficulty == 0 {
		msg.Game.BaseDifficulty = uint64(params.MinDifficulty)
	}
	if msg.Game.BaseDifficulty < uint64(params.MinDifficulty) || msg.Game.BaseDifficulty > uint64(params.MaxDifficulty) {
		return nil, status.Error(codes.InvalidArgument, "base_difficulty out of range")
	}
	if msg.Game.CreditsPerPlay == 0 {
		msg.Game.CreditsPerPlay = 1
	}
	if msg.Game.MaxPlayers == 0 {
		msg.Game.MaxPlayers = 1
	}

	if err := k.ArcadeGames.Set(ctx, msg.Game.GameId, msg.Game); err != nil {
		return nil, status.Errorf(codes.Internal, "failed to save game: %v", err)
	}
	return &types.MsgRegisterGameResponse{GameId: msg.Game.GameId}, nil
}

// UpdateGameScore is currently unimplemented.
func (k *msgServer) UpdateGameScore(ctx context.Context, msg *types.MsgUpdateGameScore) (*types.MsgUpdateGameScoreResponse, error) {
	if msg == nil {
		return nil, status.Error(codes.InvalidArgument, "invalid request")
	}
	if _, err := k.addressCodec.StringToBytes(msg.Creator); err != nil {
		return nil, status.Error(codes.InvalidArgument, "invalid creator")
	}
	if msg.ScoreDelta == 0 && msg.CurrentLevel == 0 && msg.CurrentLives == 0 {
		return nil, status.Error(codes.InvalidArgument, "no updates provided")
	}
	session, err := k.GetSession(ctx, msg.SessionId)
	if err != nil {
		return nil, status.Errorf(codes.NotFound, "session not found: %v", err)
	}
	if session.Player != msg.Creator {
		return nil, status.Error(codes.PermissionDenied, "only session owner can update score")
	}
	if session.Status != types.SessionStatusActive {
		return nil, status.Error(codes.FailedPrecondition, "session not active")
	}
	if msg.ScoreDelta > 0 {
		session.CurrentScore += msg.ScoreDelta
	}
	if msg.CurrentLevel > 0 {
		session.Level = msg.CurrentLevel
	}
	if msg.CurrentLives > 0 {
		session.Lives = msg.CurrentLives
	}

	if err := k.SetSession(ctx, session); err != nil {
		return nil, status.Errorf(codes.Internal, "failed to update session: %v", err)
	}
	if err := k.updateLeaderboard(ctx, session.Player, msg.ScoreDelta, 0, 0, 0, 0); err != nil {
		return nil, status.Errorf(codes.Internal, "failed to update leaderboard: %v", err)
	}

	return &types.MsgUpdateGameScoreResponse{TotalScore: session.CurrentScore}, nil
}

// ActivateCombo is currently unimplemented.
func (k *msgServer) ActivateCombo(ctx context.Context, msg *types.MsgActivateCombo) (*types.MsgActivateComboResponse, error) {
	if msg == nil {
		return nil, status.Error(codes.InvalidArgument, "invalid request")
	}
	if _, err := k.addressCodec.StringToBytes(msg.Creator); err != nil {
		return nil, status.Error(codes.InvalidArgument, "invalid creator")
	}
	if msg.ComboHits == 0 {
		return nil, status.Error(codes.InvalidArgument, "combo_hits must be positive")
	}
	session, err := k.GetSession(ctx, msg.SessionId)
	if err != nil {
		return nil, status.Errorf(codes.NotFound, "session not found: %v", err)
	}
	if session.Player != msg.Creator {
		return nil, status.Error(codes.PermissionDenied, "only session owner can activate combos")
	}
	if session.Status != types.SessionStatusActive {
		return nil, status.Error(codes.FailedPrecondition, "session not active")
	}

	// Combo multipliers per docs
	newMultiplier := uint64(1)
	switch {
	case msg.ComboHits >= 100:
		newMultiplier = 20
	case msg.ComboHits >= 50:
		newMultiplier = 10
	case msg.ComboHits >= 20:
		newMultiplier = 5
	case msg.ComboHits >= 10:
		newMultiplier = 3
	case msg.ComboHits >= 5:
		newMultiplier = 2
	}

	bonusScore := msg.ComboHits * 10 * newMultiplier
	session.ComboMultiplier = newMultiplier
	session.CurrentScore += bonusScore

	if err := k.SetSession(ctx, session); err != nil {
		return nil, status.Errorf(codes.Internal, "failed to update session: %v", err)
	}
	if err := k.updateLeaderboard(ctx, session.Player, bonusScore, 0, 0, 0, 0); err != nil {
		return nil, status.Errorf(codes.Internal, "failed to update leaderboard: %v", err)
	}

	return &types.MsgActivateComboResponse{Multiplier: session.ComboMultiplier, BonusScore: bonusScore}, nil
}

// UsePowerUp is currently unimplemented.
func (k *msgServer) UsePowerUp(ctx context.Context, msg *types.MsgUsePowerUp) (*types.MsgUsePowerUpResponse, error) {
	if msg == nil {
		return nil, status.Error(codes.InvalidArgument, "invalid request")
	}
	if _, err := k.addressCodec.StringToBytes(msg.Creator); err != nil {
		return nil, status.Error(codes.InvalidArgument, "invalid creator")
	}
	if msg.PowerUpId == "" {
		return nil, status.Error(codes.InvalidArgument, "power_up_id required")
	}
	session, err := k.GetSession(ctx, msg.SessionId)
	if err != nil {
		return nil, status.Errorf(codes.NotFound, "session not found: %v", err)
	}
	if session.Player != msg.Creator {
		return nil, status.Error(codes.PermissionDenied, "only session owner can use power-ups")
	}
	if session.Status != types.SessionStatusActive {
		return nil, status.Error(codes.FailedPrecondition, "session not active")
	}

	params, err := k.getParams(ctx)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to load params: %v", err)
	}

	// Charge arcade tokens for power-ups if configured
	cost := uint64(params.PowerUpCost)
	if cost > 0 {
		entry, err := k.Leaderboard.Get(ctx, msg.Creator)
		if err != nil {
			return nil, status.Error(codes.ResourceExhausted, "insufficient arcade tokens")
		}
		if entry.ArcadeTokens < cost {
			return nil, status.Error(codes.ResourceExhausted, "insufficient arcade tokens")
		}
		entry.ArcadeTokens -= cost
		if err := k.Leaderboard.Set(ctx, msg.Creator, entry); err != nil {
			return nil, status.Errorf(codes.Internal, "failed to deduct tokens: %v", err)
		}
	}

	sdkCtx := sdk.UnwrapSDKContext(ctx)
	effect := "power-up activated"

	// Track power-up usage
	session.PowerUpsCollected = append(session.PowerUpsCollected, msg.PowerUpId)
	if err := k.SetSession(ctx, session); err != nil {
		return nil, status.Errorf(codes.Internal, "failed to update session: %v", err)
	}

	sdkCtx.EventManager().EmitEvent(
		sdk.NewEvent(
			types.EventPowerUpUsed,
			sdk.NewAttribute(types.AttrSessionID, strconv.FormatUint(msg.SessionId, 10)),
			sdk.NewAttribute(types.AttrPlayer, msg.Creator),
			sdk.NewAttribute("power_up", msg.PowerUpId),
		),
	)

	return &types.MsgUsePowerUpResponse{Activated: true, Effect: effect}, nil
}

// ContinueGame is currently unimplemented.
func (k *msgServer) ContinueGame(ctx context.Context, msg *types.MsgContinueGame) (*types.MsgContinueGameResponse, error) {
	if msg == nil {
		return nil, status.Error(codes.InvalidArgument, "invalid request")
	}
	if _, err := k.addressCodec.StringToBytes(msg.Creator); err != nil {
		return nil, status.Error(codes.InvalidArgument, "invalid creator")
	}
	session, err := k.GetSession(ctx, msg.SessionId)
	if err != nil {
		return nil, status.Errorf(codes.NotFound, "session not found: %v", err)
	}
	if session.Player != msg.Creator {
		return nil, status.Error(codes.PermissionDenied, "only session owner can continue")
	}
	if session.Status != types.SessionStatusGameOver {
		return nil, status.Error(codes.FailedPrecondition, "session is not game over")
	}

	params, err := k.getParams(ctx)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to load params: %v", err)
	}

	credits, err := k.GetPlayerCredits(ctx, msg.Creator)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to get credits: %v", err)
	}

	continueCost := uint64(1)
	if params.ContinueCostMultiplier > 0 {
		continueCost = uint64(params.ContinueCostMultiplier)
	}
	if credits < continueCost {
		return nil, status.Error(codes.ResourceExhausted, "insufficient credits to continue")
	}

	if err := k.SetPlayerCredits(ctx, msg.Creator, credits-continueCost); err != nil {
		return nil, status.Errorf(codes.Internal, "failed to deduct credits: %v", err)
	}

	// Grant lives and reactivate session
	livesGranted := uint64(3)
	session.Lives += livesGranted
	session.Status = types.SessionStatusActive
	session.ContinuesUsed++

	if err := k.SetSession(ctx, session); err != nil {
		return nil, status.Errorf(codes.Internal, "failed to update session: %v", err)
	}

	return &types.MsgContinueGameResponse{ContinuesRemaining: credits - continueCost, LivesGranted: livesGranted, Cost: strconv.FormatUint(continueCost, 10)}, nil
}

// ClaimAchievement is currently unimplemented.
func (k *msgServer) ClaimAchievement(ctx context.Context, msg *types.MsgClaimAchievement) (*types.MsgClaimAchievementResponse, error) {
	if msg == nil {
		return nil, status.Error(codes.InvalidArgument, "invalid request")
	}
	if _, err := k.addressCodec.StringToBytes(msg.Creator); err != nil {
		return nil, status.Error(codes.InvalidArgument, "invalid creator")
	}
	if msg.AchievementId == "" {
		return nil, status.Error(codes.InvalidArgument, "achievement_id required")
	}

	key := achievementKey(msg.Creator, msg.AchievementId)
	_, getErr := k.Achievements.Get(ctx, key)
	if getErr == nil {
		return nil, status.Error(codes.AlreadyExists, "achievement already claimed")
	}
	if getErr != nil && !errors.Is(getErr, collections.ErrNotFound) {
		return nil, status.Errorf(codes.Internal, "failed to check achievement: %v", getErr)
	}

	rewardTokens, ok, err := k.Keeper.canClaimAchievement(ctx, msg.Creator, msg.AchievementId, msg.GameId)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to evaluate achievement: %v", err)
	}
	if !ok {
		return nil, status.Error(codes.FailedPrecondition, "achievement not unlocked")
	}

	sdkCtx := sdk.UnwrapSDKContext(ctx)
	unlockedAt := sdkCtx.BlockTime()
	ach := types.PlayerAchievement{
		Player:        msg.Creator,
		AchievementId: msg.AchievementId,
		GameId:        msg.GameId,
		UnlockedAt:    &unlockedAt,
		RewardTokens:  rewardTokens,
	}

	if err := k.Achievements.Set(ctx, key, ach); err != nil {
		return nil, status.Errorf(codes.Internal, "failed to store achievement: %v", err)
	}
	if err := k.updateLeaderboard(ctx, msg.Creator, 0, 0, 1, 0, rewardTokens); err != nil {
		return nil, status.Errorf(codes.Internal, "failed to update leaderboard: %v", err)
	}

	return &types.MsgClaimAchievementResponse{TokensAwarded: rewardTokens, AchievementName: msg.AchievementId}, nil
}

// CreateTournament is currently unimplemented.
func (k *msgServer) CreateTournament(ctx context.Context, msg *types.MsgCreateTournament) (*types.MsgCreateTournamentResponse, error) {
	if msg == nil {
		return nil, status.Error(codes.InvalidArgument, "invalid request")
	}
	if msg.Tournament.TournamentId == "" {
		return nil, status.Error(codes.InvalidArgument, "tournament_id required")
	}
	if _, err := k.addressCodec.StringToBytes(msg.Creator); err != nil {
		return nil, status.Error(codes.InvalidArgument, "invalid creator")
	}
	if msg.Tournament.GameId == "" || msg.Tournament.Name == "" {
		return nil, status.Error(codes.InvalidArgument, "name and game_id required")
	}
	if msg.Tournament.StartTime != nil && msg.Tournament.EndTime != nil && msg.Tournament.EndTime.Before(*msg.Tournament.StartTime) {
		return nil, status.Error(codes.InvalidArgument, "end_time before start_time")
	}

	if _, err := k.Tournaments.Get(ctx, msg.Tournament.TournamentId); err == nil {
		return nil, status.Error(codes.AlreadyExists, "tournament exists")
	}

	params, err := k.getParams(ctx)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to load params: %v", err)
	}
	if msg.Tournament.EntryFee == 0 {
		msg.Tournament.EntryFee = params.TournamentRegistrationFee
	}
	if msg.Tournament.PrizePool == 0 {
		msg.Tournament.PrizePool = 0
	}

	if msg.Tournament.Status == types.TournamentStatus_TOURNAMENT_UNSPECIFIED {
		msg.Tournament.Status = types.TournamentStatus_TOURNAMENT_REGISTRATION
	}
	if err := k.Tournaments.Set(ctx, msg.Tournament.TournamentId, msg.Tournament); err != nil {
		return nil, status.Errorf(codes.Internal, "failed to store tournament: %v", err)
	}
	return &types.MsgCreateTournamentResponse{TournamentId: msg.Tournament.TournamentId}, nil
}

// JoinTournament is currently unimplemented.
func (k *msgServer) JoinTournament(ctx context.Context, msg *types.MsgJoinTournament) (*types.MsgJoinTournamentResponse, error) {
	if msg == nil {
		return nil, status.Error(codes.InvalidArgument, "invalid request")
	}
	if _, err := k.addressCodec.StringToBytes(msg.Creator); err != nil {
		return nil, status.Error(codes.InvalidArgument, "invalid creator")
	}
	if msg.TournamentId == "" {
		return nil, status.Error(codes.InvalidArgument, "tournament_id required")
	}
	tour, err := k.Tournaments.Get(ctx, msg.TournamentId)
	if err != nil {
		return nil, status.Error(codes.NotFound, "tournament not found")
	}
	if tour.Status != types.TournamentStatus_TOURNAMENT_REGISTRATION && tour.Status != types.TournamentStatus_TOURNAMENT_ACTIVE {
		return nil, status.Error(codes.FailedPrecondition, "tournament not open")
	}

	for _, p := range tour.Participants {
		if p.Player == msg.Creator {
			return &types.MsgJoinTournamentResponse{Joined: true, ParticipantCount: uint64(len(tour.Participants))}, nil
		}
	}

	if tour.EntryFee > 0 {
		if err := k.Keeper.deductArcadeTokens(ctx, msg.Creator, tour.EntryFee); err != nil {
			return nil, status.Error(codes.ResourceExhausted, "insufficient arcade tokens")
		}
		tour.PrizePool += tour.EntryFee
	}

	tour.Participants = append(tour.Participants, &types.TournamentParticipant{Player: msg.Creator, Qualified: true})
	if err := k.Tournaments.Set(ctx, msg.TournamentId, tour); err != nil {
		return nil, status.Errorf(codes.Internal, "failed to update tournament: %v", err)
	}
	return &types.MsgJoinTournamentResponse{Joined: true, ParticipantCount: uint64(len(tour.Participants))}, nil
}

// SubmitTournamentScore is currently unimplemented.
func (k *msgServer) SubmitTournamentScore(ctx context.Context, msg *types.MsgSubmitTournamentScore) (*types.MsgSubmitTournamentScoreResponse, error) {
	if msg == nil {
		return nil, status.Error(codes.InvalidArgument, "invalid request")
	}
	if _, err := k.addressCodec.StringToBytes(msg.Creator); err != nil {
		return nil, status.Error(codes.InvalidArgument, "invalid creator")
	}
	if msg.Score == 0 {
		return nil, status.Error(codes.InvalidArgument, "score must be positive")
	}
	tour, err := k.Tournaments.Get(ctx, msg.TournamentId)
	if err != nil {
		return nil, status.Error(codes.NotFound, "tournament not found")
	}
	if tour.Status != types.TournamentStatus_TOURNAMENT_ACTIVE {
		return nil, status.Error(codes.FailedPrecondition, "tournament not active")
	}

	found := false
	for i := range tour.Participants {
		if tour.Participants[i].Player == msg.Creator {
			found = true
			if msg.Score > tour.Participants[i].BestScore {
				tour.Participants[i].BestScore = msg.Score
			}
			break
		}
	}
	if !found {
		return nil, status.Error(codes.NotFound, "participant not found")
	}

	// Re-rank participants
	sort.Slice(tour.Participants, func(i, j int) bool {
		return tour.Participants[i].BestScore > tour.Participants[j].BestScore
	})

	var currentRank uint64
	for i := range tour.Participants {
		tour.Participants[i].Rank = uint64(i + 1)
		if tour.Participants[i].Player == msg.Creator {
			currentRank = tour.Participants[i].Rank
		}
	}

	if err := k.Tournaments.Set(ctx, msg.TournamentId, tour); err != nil {
		return nil, status.Errorf(codes.Internal, "failed to update tournament: %v", err)
	}

	qualified := currentRank <= uint64(len(tour.Participants))/2 || currentRank == 1
	return &types.MsgSubmitTournamentScoreResponse{CurrentRank: currentRank, Qualified: qualified}, nil
}

// SetHighScoreInitials is currently unimplemented.
func (k *msgServer) SetHighScoreInitials(ctx context.Context, msg *types.MsgSetHighScoreInitials) (*types.MsgSetHighScoreInitialsResponse, error) {
	if msg == nil {
		return nil, status.Error(codes.InvalidArgument, "invalid request")
	}
	if _, err := k.addressCodec.StringToBytes(msg.Creator); err != nil {
		return nil, status.Error(codes.InvalidArgument, "invalid creator")
	}
	if msg.GameId == "" || msg.Initials == "" {
		return nil, status.Error(codes.InvalidArgument, "game_id and initials required")
	}
	initials := strings.ToUpper(msg.Initials)
	if !initialsRe.MatchString(initials) {
		return nil, status.Error(codes.InvalidArgument, "initials must be exactly 3 letters A-Z")
	}

	var updated bool
	err := k.HighScores.Walk(ctx, nil, func(id uint64, hs types.HighScore) (bool, error) {
		if hs.GameId == msg.GameId && hs.Player == msg.Creator {
			hs.Initials = initials
			updated = true
			return true, k.HighScores.Set(ctx, id, hs)
		}
		return false, nil
	})
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to update initials: %v", err)
	}
	if !updated {
		return nil, status.Error(codes.NotFound, "high score not found")
	}
	return &types.MsgSetHighScoreInitialsResponse{Updated: true}, nil
}
