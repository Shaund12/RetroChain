package types

import (
	"fmt"

	math "cosmossdk.io/math"
	paramstypes "github.com/cosmos/cosmos-sdk/x/params/types"
)

var (
	KeyFeeBurnRate       = []byte("FeeBurnRate")
	KeyProvisionBurnRate = []byte("ProvisionBurnRate")
)

// ParamKeyTable returns the key declaration for params.
func ParamKeyTable() paramstypes.KeyTable {
	return paramstypes.NewKeyTable().RegisterParamSet(&Params{})
}

// ParamSetPairs implements params.ParamSet.
func (p *Params) ParamSetPairs() paramstypes.ParamSetPairs {
	return paramstypes.ParamSetPairs{
		paramstypes.NewParamSetPair(KeyFeeBurnRate, &p.FeeBurnRate, validateDec("fee_burn_rate")),
		paramstypes.NewParamSetPair(KeyProvisionBurnRate, &p.ProvisionBurnRate, validateDec("provision_burn_rate")),
	}
}

func validateDec(name string) paramstypes.ValueValidatorFn {
	return func(i interface{}) error {
		dec, ok := i.(math.LegacyDec)
		if !ok {
			// attempt pointer
			if dptr, ok2 := i.(*math.LegacyDec); ok2 {
				dec = *dptr
			} else {
				return fmt.Errorf("invalid type for %s", name)
			}
		}
		return validateRate(dec, name)
	}
}

// Validate performs basic validation.
// ValidateBasic performs basic validation.
func (p Params) ValidateBasic() error { return p.Validate() }
