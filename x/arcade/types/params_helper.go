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
// Note: The Params struct is generated from protobuf. The proto file defines the fields
// but they need to be regenerated with `make proto-gen` to be reflected in params.pb.go.
func DefaultParams() Params {
	return Params{}
}

// Validate performs basic validation of module parameters.
// Currently returns nil as the generated Params struct is empty.
// This should be updated after proto regeneration.
func (p Params) Validate() error {
	return nil
}
