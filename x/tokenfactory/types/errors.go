package types

import (
	errorsmod "cosmossdk.io/errors"
)

var (
	ErrInvalidSubdenom    = errorsmod.Register(ModuleName, 1, "invalid subdenom")
	ErrDenomAlreadyExists = errorsmod.Register(ModuleName, 2, "denom already exists")
	ErrUnauthorized       = errorsmod.Register(ModuleName, 3, "unauthorized")
	ErrUnknownDenom       = errorsmod.Register(ModuleName, 4, "unknown denom")
)
