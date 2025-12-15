package types

import (
	"strings"
)

// DefaultParams returns default params.
func DefaultParams() Params {
	return Params{AllowedDenom: ""}
}

// Validate validates module params.
func (p Params) Validate() error {
	// allowed denom can be empty (module disabled until set via gov/genesis).
	if strings.TrimSpace(p.AllowedDenom) == "" {
		return nil
	}
	// Basic sanity: IBC denoms are typically "ibc/..."; allow any non-empty denom string.
	return nil
}
