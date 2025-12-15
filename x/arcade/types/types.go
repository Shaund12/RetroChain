package types

// Session status helper aliases to the proto enums for readability in keeper code.
const (
	SessionStatusActive    = SessionStatus_STATUS_ACTIVE
	SessionStatusCompleted = SessionStatus_STATUS_COMPLETED
	SessionStatusGameOver  = SessionStatus_STATUS_GAME_OVER
)

// PlayerCredits represents a player's available credits for arcade games.
type PlayerCredits struct {
	Player  string `json:"player"`
	Credits uint64 `json:"credits"`
}
