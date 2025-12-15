package types

import "cosmossdk.io/collections"

const (
	// ModuleName defines the module name
	ModuleName = "arcade"

	// StoreKey defines the primary module store key
	StoreKey = ModuleName

	// RouterKey is the message route for the module
	RouterKey = ModuleName

	// MemStoreKey defines the in-memory store key
	MemStoreKey = "mem_arcade"

	// GovModuleName duplicates the gov module's name to avoid a dependency with x/gov.
	// It should be synced with the gov module's name if it is ever changed.
	// See: https://github.com/cosmos/cosmos-sdk/blob/v0.52.0-beta.2/x/gov/types/keys.go#L9
	GovModuleName = "gov"
)

// Storage prefixes
var (
	// ParamsKey is the prefix to retrieve all Params
	ParamsKey = collections.NewPrefix("p_arcade")
	// PlayerCreditsKeyPrefix is the prefix for player credits storage
	PlayerCreditsKeyPrefix = collections.NewPrefix("pc_arcade")
	// GameSessionKeyPrefix is the prefix for game sessions storage
	GameSessionKeyPrefix = collections.NewPrefix("gs_arcade")
	// SessionCounterKey is the key for the session counter
	SessionCounterKey = collections.NewPrefix("sc_arcade")
	// ArcadeGameKeyPrefix is the prefix for registered games
	ArcadeGameKeyPrefix = collections.NewPrefix("ag_arcade")
	// HighScoreKeyPrefix is the prefix for high score records
	HighScoreKeyPrefix = collections.NewPrefix("hs_arcade")
	// HighScoreCounterKey tracks high score ids
	HighScoreCounterKey = collections.NewPrefix("hsc_arcade")
	// LeaderboardKeyPrefix stores per-player leaderboard entries
	LeaderboardKeyPrefix = collections.NewPrefix("lb_arcade")
	// AchievementKeyPrefix stores player achievements keyed by player/achievement id
	AchievementKeyPrefix = collections.NewPrefix("ach_arcade")
	// TournamentKeyPrefix stores tournaments keyed by tournament id
	TournamentKeyPrefix = collections.NewPrefix("t_arcade")
	// PlayerCoinsInsertedKeyPrefix stores total coins inserted (credits purchased) per player
	PlayerCoinsInsertedKeyPrefix = collections.NewPrefix("pci_arcade")
	// PlayerLastCoinInsertTimeKeyPrefix stores last coin insert unix time per player
	PlayerLastCoinInsertTimeKeyPrefix = collections.NewPrefix("plcit_arcade")
	// PlayerQuickStartAchievedKeyPrefix stores whether player has achieved quick-start condition
	PlayerQuickStartAchievedKeyPrefix = collections.NewPrefix("pqsa_arcade")
)

// KeyPrefix returns a key prefix from a string
func KeyPrefix(p string) []byte { return []byte(p) }
