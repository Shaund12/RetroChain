package types

func DefaultGenesis() *GenesisState {
	return &GenesisState{
		ClassAuthorities: []ClassAuthority{},
		CreatorClasses:   []CreatorClass{},
	}
}
