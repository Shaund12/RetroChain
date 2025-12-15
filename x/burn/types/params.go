package types

import (
	"fmt"

	math "cosmossdk.io/math"
)

// Params defines burn configuration.
type Params struct {
	FeeBurnRate       math.LegacyDec `json:"fee_burn_rate" yaml:"fee_burn_rate"`
	ProvisionBurnRate math.LegacyDec `json:"provision_burn_rate" yaml:"provision_burn_rate"`
}

// DefaultParams returns conservative defaults.
func DefaultParams() Params {
	return Params{
		FeeBurnRate:       math.LegacyNewDecWithPrec(5, 2), // 0.05
		ProvisionBurnRate: math.LegacyNewDecWithPrec(0, 2), // 0.00
	}
}

// Validate checks param bounds.
func (p Params) Validate() error {
	if err := validateRate(p.FeeBurnRate, "fee_burn_rate"); err != nil {
		return err
	}
	if err := validateRate(p.ProvisionBurnRate, "provision_burn_rate"); err != nil {
		return err
	}
	return nil
}

func validateRate(v math.LegacyDec, name string) error {
	if v.IsNil() {
		return fmt.Errorf("%s cannot be nil", name)
	}
	if v.IsNegative() {
		return fmt.Errorf("%s cannot be negative", name)
	}
	// hard cap to prevent accidental total burn
	if v.GT(math.LegacyNewDecWithPrec(9, 1)) { // 0.9
		return fmt.Errorf("%s cannot exceed 0.9", name)
	}
	return nil
}
