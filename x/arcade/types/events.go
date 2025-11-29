package types

const (
	EventGameStarted         = "arcade.game_started"
	EventScoreUpdated        = "arcade.score_updated"
	EventComboActivated      = "arcade.combo_activated"
	EventPowerUpUsed         = "arcade.power_up_used"
	EventHighScore           = "arcade.high_score"
	EventAchievementUnlocked = "arcade.achievement_unlocked"
	EventTournamentJoined    = "arcade.tournament_joined"
	EventSessionEnded        = "arcade.session_ended"
	EventGameOver            = "arcade.game_over"
	EventRewardDistributed   = "arcade.reward_distributed"
	EventCreditsInserted     = "arcade.credits_inserted"
)

const (
	AttrGameID       = "game_id"
	AttrSessionID    = "session_id"
	AttrPlayer       = "player"
	AttrScore        = "score"
	AttrLevel        = "level"
	AttrComboHits    = "combo_hits"
	AttrPowerUpID    = "power_up_id"
	AttrInitials     = "initials"
	AttrTournament   = "tournament_id"
	AttrRewardAmount = "reward_amount"
	AttrCredits      = "credits"
)
