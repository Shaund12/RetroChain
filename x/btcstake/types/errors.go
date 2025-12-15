package types

import "cosmossdk.io/errors"

// DONTCOVER

var (
	ErrInvalidSigner     = errors.Register(ModuleName, 1199, "invalid signer")
	ErrInvalidAmount     = errors.Register(ModuleName, 1200, "invalid amount")
	ErrParamsNotSet      = errors.Register(ModuleName, 1201, "params not set")
	ErrInvalidDenom      = errors.Register(ModuleName, 1202, "invalid denom")
	ErrInsufficientStake = errors.Register(ModuleName, 1203, "insufficient staked amount")
)
