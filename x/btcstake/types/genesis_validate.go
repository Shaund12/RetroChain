package types

// Validate performs basic genesis validation.
func (gs GenesisState) Validate() error {
	return gs.Params.Validate()
}
