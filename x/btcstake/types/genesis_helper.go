package types

// DefaultGenesis returns a default genesis state.
func DefaultGenesis() *GenesisState {
	return &GenesisState{Params: DefaultParams()}
}
