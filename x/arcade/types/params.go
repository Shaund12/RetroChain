package types

import (
	fmt "fmt"
)

// Params holds configurable parameters for arcade module.
type Params struct {
	BaseCreditsCost            uint64 // cost per credit in uretro
	TokensPerThousandPoints    uint64 // reward rate
	MaxActiveSessions          uint32 // max concurrent sessions per player
	ContinueCostMultiplier     uint32 // percent increase per continue
	HighScoreReward            uint64 // bonus tokens for high score
	TournamentRegistrationFee  uint64 // entry fee in uretro
	MinDifficulty              uint32 // 1
	MaxDifficulty              uint32 // 10
	AchievementRewardMultiplier uint32 // multiplier for achievement rewards
	PowerUpCost                uint64 // cost to use power-up in uretro
}

func DefaultParams() Params {
	return Params{
		BaseCreditsCost:             1000000,
		TokensPerThousandPoints:     1,
		MaxActiveSessions:           3,
		ContinueCostMultiplier:      150,
		HighScoreReward:             100,
		TournamentRegistrationFee:   10000000,
		MinDifficulty:               1,
		MaxDifficulty:               10,
		AchievementRewardMultiplier: 2,
		PowerUpCost:                 500000,
	}
}

func (p Params) Validate() error {
	if p.MinDifficulty == 0 || p.MaxDifficulty < p.MinDifficulty {
		return fmt.Errorf("invalid difficulty range")
	}
	if p.BaseCreditsCost == 0 {
		return fmt.Errorf("base credits cost must be > 0")
	}
	return nil
}
