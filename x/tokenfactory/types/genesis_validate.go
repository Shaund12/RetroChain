package types

import (
	"fmt"
)

func (gs GenesisState) Validate() error {
	// Keep validation lightweight; address validation happens when initializing.
	seenDenoms := make(map[string]struct{}, len(gs.DenomAuthorities))
	for _, da := range gs.DenomAuthorities {
		if da.Denom == "" {
			return fmt.Errorf("denom_authorities: denom required")
		}
		if da.Admin == "" {
			return fmt.Errorf("denom_authorities: admin required")
		}
		if _, ok := seenDenoms[da.Denom]; ok {
			return fmt.Errorf("denom_authorities: duplicate denom %q", da.Denom)
		}
		seenDenoms[da.Denom] = struct{}{}
	}

	for _, cd := range gs.CreatorDenoms {
		if cd.Creator == "" {
			return fmt.Errorf("creator_denoms: creator required")
		}
		if cd.Denom == "" {
			return fmt.Errorf("creator_denoms: denom required")
		}
	}

	return nil
}
