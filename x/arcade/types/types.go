package types

// GameSession represents an active game session in the arcade.
type GameSession struct {
	SessionID    uint64 `json:"session_id"`
	GameID       string `json:"game_id"`
	Player       string `json:"player"`
	CreditsUsed  uint64 `json:"credits_used"`
	CurrentScore uint64 `json:"current_score"`
	Status       string `json:"status"`
	StartTime    int64  `json:"start_time"`
	EndTime      int64  `json:"end_time,omitempty"`
}

// Session status constants
const (
	SessionStatusActive    = "STATUS_ACTIVE"
	SessionStatusCompleted = "STATUS_COMPLETED"
	SessionStatusGameOver  = "STATUS_GAME_OVER"
)

// PlayerCredits represents a player's available credits for arcade games.
type PlayerCredits struct {
	Player  string `json:"player"`
	Credits uint64 `json:"credits"`
}
