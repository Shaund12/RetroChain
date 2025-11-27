package types

import (
	errorsmod "cosmossdk.io/errors"
)

var (
	ErrInvalidRequest   = errorsmod.Register(ModuleName, 1, "invalid request")
	ErrNotFound         = errorsmod.Register(ModuleName, 2, "not found")
	ErrUnauthorized     = errorsmod.Register(ModuleName, 3, "unauthorized")
	ErrInsufficientFund = errorsmod.Register(ModuleName, 4, "insufficient funds or credits")
	ErrLimitExceeded    = errorsmod.Register(ModuleName, 5, "limit exceeded")
	ErrInvalidSigner    = errorsmod.Register(ModuleName, 6, "expected gov account as only signer for proposal message")
)
