package types

import (
	paramstypes "github.com/cosmos/cosmos-sdk/x/params/types"
)

// ParamKeyTable returns the parameter key table.
func ParamKeyTable() paramstypes.KeyTable {
	return paramstypes.NewKeyTable().RegisterParamSet(&Params{})
}

// ParamSetPairs implements params.ParamSet
func (p *Params) ParamSetPairs() paramstypes.ParamSetPairs {
	return paramstypes.ParamSetPairs{}
}

// DefaultParams returns default module parameters.
// TODO: The Params struct is currently empty because the protobuf files need regeneration.
// Run `ignite generate proto-go` or `buf generate` to populate the Params struct with
// the fields defined in proto/retrochain/arcade/v1/params.proto.
// After regeneration, update this function to return proper default values.
func DefaultParams() Params {
	return Params{}
}

// Validate performs basic validation of module parameters.
// TODO: After protobuf regeneration, implement proper validation for all parameter fields.
func (p Params) Validate() error {
	return nil
}
