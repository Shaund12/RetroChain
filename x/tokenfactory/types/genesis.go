package types

func DefaultGenesis() *GenesisState {
	return &GenesisState{
		DenomAuthorities: []DenomAuthority{},
		CreatorDenoms:    []CreatorDenom{},
	}
}
