package types

import (
	"fmt"

	paramstypes "github.com/cosmos/cosmos-sdk/x/params/types"
)

// ParamKeyTable returns the parameter key table.
func ParamKeyTable() paramstypes.KeyTable {
	return paramstypes.NewKeyTable().RegisterParamSet(&Params{})
}

// ParamSetPairs implements params.ParamSet
func (p *Params) ParamSetPairs() paramstypes.ParamSetPairs {
	return paramstypes.ParamSetPairs{}
}

// DefaultParams returns default module parameters.
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
		PowerUpCost:                 500,
	}
}

// Validate performs basic validation of module parameters.
func (p Params) Validate() error {
	if p.MinDifficulty == 0 || p.MaxDifficulty < p.MinDifficulty {
		return fmt.Errorf("invalid difficulty range")
	}
	if p.BaseCreditsCost == 0 {
		return fmt.Errorf("base credits cost must be > 0")
	}
	return nil
}
