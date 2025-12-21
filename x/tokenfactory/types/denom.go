package types

import (
	"fmt"
	"strings"

	sdk "github.com/cosmos/cosmos-sdk/types"
)

const FactoryDenomPrefix = "factory/"

func BuildFactoryDenom(creator, subdenom string) (string, error) {
	subdenom = strings.TrimSpace(subdenom)
	if err := ValidateSubdenom(subdenom); err != nil {
		return "", err
	}
	denom := fmt.Sprintf("%s%s/%s", FactoryDenomPrefix, creator, subdenom)
	if err := sdk.ValidateDenom(denom); err != nil {
		return "", err
	}
	return denom, nil
}

func ValidateSubdenom(subdenom string) error {
	if subdenom == "" {
		return ErrInvalidSubdenom
	}
	// Keep it simple and safe: no path separators.
	if strings.Contains(subdenom, "/") {
		return ErrInvalidSubdenom
	}
	// sdk.ValidateDenom will also enforce length/charset once embedded.
	return nil
}
