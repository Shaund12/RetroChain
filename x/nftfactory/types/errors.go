package types

import errorsmod "cosmossdk.io/errors"

var (
	ErrInvalidSubID       = errorsmod.Register(ModuleName, 1, "invalid sub_id")
	ErrClassAlreadyExists = errorsmod.Register(ModuleName, 2, "class already exists")
	ErrUnauthorized       = errorsmod.Register(ModuleName, 3, "unauthorized")
	ErrUnknownClass       = errorsmod.Register(ModuleName, 4, "unknown class")
)
