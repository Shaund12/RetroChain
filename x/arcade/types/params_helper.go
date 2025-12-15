package types

import (
	"fmt"

	paramstypes "github.com/cosmos/cosmos-sdk/x/params/types"
)

// Parameter keys
var (
	KeyBaseCreditsCost             = []byte("BaseCreditsCost")
	KeyTokensPerThousandPoints     = []byte("TokensPerThousandPoints")
	KeyMaxActiveSessions           = []byte("MaxActiveSessions")
	KeyContinueCostMultiplier      = []byte("ContinueCostMultiplier")
	KeyHighScoreReward             = []byte("HighScoreReward")
	KeyTournamentRegistrationFee   = []byte("TournamentRegistrationFee")
	KeyMinDifficulty               = []byte("MinDifficulty")
	KeyMaxDifficulty               = []byte("MaxDifficulty")
	KeyAchievementRewardMultiplier = []byte("AchievementRewardMultiplier")
	KeyPowerUpCost                 = []byte("PowerUpCost")
)

// Default parameter values tuned for a reasonable arcade experience.
const (
	DefaultBaseCreditsCost             uint64 = 1_000_000 // 1 uretro credit cost aligns with TokensPerCredit
	DefaultTokensPerThousandPoints     uint32 = 10        // 10 uretro per 1000 points
	DefaultMaxActiveSessions           uint32 = 3
	DefaultContinueCostMultiplier      uint32 = 1 // cost expressed as credits
	DefaultHighScoreReward             uint32 = 100
	DefaultTournamentRegistrationFee   uint64 = 0
	DefaultMinDifficulty               uint32 = 1
	DefaultMaxDifficulty               uint32 = 10
	DefaultAchievementRewardMultiplier uint32 = 5
	DefaultPowerUpCost                 uint32 = 5
)

// ParamKeyTable returns the parameter key table.
func ParamKeyTable() paramstypes.KeyTable {
	return paramstypes.NewKeyTable().RegisterParamSet(&Params{})
}

// ParamSetPairs implements params.ParamSet.
func (p *Params) ParamSetPairs() paramstypes.ParamSetPairs {
	return paramstypes.ParamSetPairs{
		paramstypes.NewParamSetPair(KeyBaseCreditsCost, &p.BaseCreditsCost, validateNonZeroUint64("base_credits_cost")),
		paramstypes.NewParamSetPair(KeyTokensPerThousandPoints, &p.TokensPerThousandPoints, validatePositiveUint32("tokens_per_thousand_points")),
		paramstypes.NewParamSetPair(KeyMaxActiveSessions, &p.MaxActiveSessions, validateUint32("max_active_sessions")),
		paramstypes.NewParamSetPair(KeyContinueCostMultiplier, &p.ContinueCostMultiplier, validatePositiveUint32("continue_cost_multiplier")),
		paramstypes.NewParamSetPair(KeyHighScoreReward, &p.HighScoreReward, validateNonZeroUint32("high_score_reward")),
		paramstypes.NewParamSetPair(KeyTournamentRegistrationFee, &p.TournamentRegistrationFee, validateUint64("tournament_registration_fee")),
		paramstypes.NewParamSetPair(KeyMinDifficulty, &p.MinDifficulty, validateDifficultyBound("min_difficulty")),
		paramstypes.NewParamSetPair(KeyMaxDifficulty, &p.MaxDifficulty, validateDifficultyBound("max_difficulty")),
		paramstypes.NewParamSetPair(KeyAchievementRewardMultiplier, &p.AchievementRewardMultiplier, validatePositiveUint32("achievement_reward_multiplier")),
		paramstypes.NewParamSetPair(KeyPowerUpCost, &p.PowerUpCost, validateUint32("power_up_cost")),
	}
}

// DefaultParams returns default module parameters.
func DefaultParams() Params {
	return Params{
		BaseCreditsCost:             DefaultBaseCreditsCost,
		TokensPerThousandPoints:     DefaultTokensPerThousandPoints,
		MaxActiveSessions:           DefaultMaxActiveSessions,
		ContinueCostMultiplier:      DefaultContinueCostMultiplier,
		HighScoreReward:             DefaultHighScoreReward,
		TournamentRegistrationFee:   DefaultTournamentRegistrationFee,
		MinDifficulty:               DefaultMinDifficulty,
		MaxDifficulty:               DefaultMaxDifficulty,
		AchievementRewardMultiplier: DefaultAchievementRewardMultiplier,
		PowerUpCost:                 DefaultPowerUpCost,
	}
}

// Validate performs basic validation of module parameters.
func (p Params) Validate() error {
	if err := validateNonZeroUint64("base_credits_cost")(p.BaseCreditsCost); err != nil {
		return err
	}
	if err := validatePositiveUint32("tokens_per_thousand_points")(p.TokensPerThousandPoints); err != nil {
		return err
	}
	if err := validateUint32("max_active_sessions")(p.MaxActiveSessions); err != nil {
		return err
	}
	if err := validatePositiveUint32("continue_cost_multiplier")(p.ContinueCostMultiplier); err != nil {
		return err
	}
	if err := validateNonZeroUint32("high_score_reward")(p.HighScoreReward); err != nil {
		return err
	}
	if err := validateUint64("tournament_registration_fee")(p.TournamentRegistrationFee); err != nil {
		return err
	}
	if err := validateDifficultyBound("min_difficulty")(p.MinDifficulty); err != nil {
		return err
	}
	if err := validateDifficultyBound("max_difficulty")(p.MaxDifficulty); err != nil {
		return err
	}
	if p.MinDifficulty > p.MaxDifficulty {
		return fmt.Errorf("min_difficulty cannot exceed max_difficulty")
	}
	if err := validatePositiveUint32("achievement_reward_multiplier")(p.AchievementRewardMultiplier); err != nil {
		return err
	}
	return validateUint32("power_up_cost")(p.PowerUpCost)
}

func validateNonZeroUint64(name string) paramstypes.ValueValidatorFn {
	return func(i interface{}) error {
		v, ok := i.(uint64)
		if !ok {
			return fmt.Errorf("invalid parameter type for %s", name)
		}
		if v == 0 {
			return fmt.Errorf("%s must be positive", name)
		}
		return nil
	}
}

func validateUint64(name string) paramstypes.ValueValidatorFn {
	return func(i interface{}) error {
		_, ok := i.(uint64)
		if !ok {
			return fmt.Errorf("invalid parameter type for %s", name)
		}
		return nil
	}
}

func validatePositiveUint32(name string) paramstypes.ValueValidatorFn {
	return func(i interface{}) error {
		v, ok := i.(uint32)
		if !ok {
			return fmt.Errorf("invalid parameter type for %s", name)
		}
		if v == 0 {
			return fmt.Errorf("%s must be positive", name)
		}
		return nil
	}
}

func validateNonZeroUint32(name string) paramstypes.ValueValidatorFn {
	return func(i interface{}) error {
		v, ok := i.(uint32)
		if !ok {
			return fmt.Errorf("invalid parameter type for %s", name)
		}
		if v == 0 {
			return fmt.Errorf("%s must be positive", name)
		}
		return nil
	}
}

func validateUint32(name string) paramstypes.ValueValidatorFn {
	return func(i interface{}) error {
		_, ok := i.(uint32)
		if !ok {
			return fmt.Errorf("invalid parameter type for %s", name)
		}
		return nil
	}
}

func validateDifficultyBound(name string) paramstypes.ValueValidatorFn {
	return func(i interface{}) error {
		v, ok := i.(uint32)
		if !ok {
			return fmt.Errorf("invalid parameter type for %s", name)
		}
		if v < 1 || v > 10 {
			return fmt.Errorf("%s must be between 1 and 10", name)
		}
		return nil
	}
}
