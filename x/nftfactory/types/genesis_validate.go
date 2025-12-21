package types

import "strings"

func (gs GenesisState) Validate() error {
	// Minimal validation; addresses and IDs are validated on use.
	for _, ca := range gs.ClassAuthorities {
		if strings.TrimSpace(ca.ClassId) == "" || strings.TrimSpace(ca.Admin) == "" {
			return ErrUnknownClass
		}
	}
	for _, cc := range gs.CreatorClasses {
		if strings.TrimSpace(cc.Creator) == "" || strings.TrimSpace(cc.ClassId) == "" {
			return ErrUnknownClass
		}
	}
	return nil
}
