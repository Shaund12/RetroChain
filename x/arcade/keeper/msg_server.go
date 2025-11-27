package keeper

import (
	"context"
)

// MsgServer implements arcade Msg RPCs. Fill logic per proto-generated interface.
type MsgServer struct {
	Keeper
}

func NewMsgServerImpl(k Keeper) MsgServer { return MsgServer{Keeper: k} }

// TODO: implement handlers for:
// - InsertCoin
// - StartSession
// - UpdateGameScore
// - ActivateCombo
// - UsePowerUp
// - ContinueGame
// - SubmitScore
// - SetHighScoreInitials
// - RegisterGame
// - CreateTournament
// - JoinTournament
// - SubmitTournamentScore
// - ClaimAchievement

// Example stub (replace with generated signatures):
func (s MsgServer) InsertCoin(ctx context.Context, req interface{}) (interface{}, error) {
	return nil, nil
}
