package types

import (
	"fmt"

	math "cosmossdk.io/math"
)

// DefaultParams returns conservative defaults.
func DefaultParams() Params {
	return Params{
		FeeBurnRate:       math.LegacyNewDecWithPrec(5, 2), // 0.05
		ProvisionBurnRate: math.LegacyNewDecWithPrec(0, 2), // 0.00
	}
}

// ZeroParams returns a zeroed params.
func ZeroParams() Params {
	return Params{FeeBurnRate: math.LegacyZeroDec(), ProvisionBurnRate: math.LegacyZeroDec()}
}

// Copy returns a shallow copy.
func (p Params) Copy() Params {
	return Params{FeeBurnRate: p.FeeBurnRate, ProvisionBurnRate: p.ProvisionBurnRate}
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

// UnpackInterfaces exists for codec compatibility.
func (p *Params) UnpackInterfaces(_ interface{}) error { return nil }

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
